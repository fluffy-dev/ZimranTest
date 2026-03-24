from __future__ import annotations

import uuid

from src.quiz.dependencies.repository import IQuizRepository

from src.attempt.enum import AttemptStatusEnum
from src.attempt.dependencies.repository import IAttemptRepository, IOutboxRepository
from src.attempt.dependencies.grading_service import IGradingService
from src.attempt.dto import AttemptResultResponseDTO, QuestionResultItemDTO, SubmitAttemptDTO, AttemptStartResponseDTO

from src.config.project import settings as project_settings
from shared.exceptions import AttemptAlreadyCompletedException, NotFoundException
from shared.logging import get_logger
from shared.schemas import QuizRewardEvent, QuizRewardPayload

logger = get_logger(__name__)


class AttemptService:
    """
    Orchestrates the lifecycle of a quiz attempt, including initiation, 
    grading, reward calculation, and outbox event triggering.
    """

    def __init__(
        self,
        attempt_repo: IAttemptRepository,
        quiz_repo: IQuizRepository,
        outbox_repo: IOutboxRepository,
        grading_service: IGradingService,
    ) -> None:
        """
        Initializes the AttemptService with required repositories and services.

        Args:
            attempt_repo: Repository for attempt data persistence.
            quiz_repo: Repository for quiz and question data.
            outbox_repo: Repository for transactional outbox events.
            grading_service: Service for checking answer correctness.
        """
        self._quiz_repo = quiz_repo
        self._attempt_repo = attempt_repo
        self._outbox_repo = outbox_repo
        self._grading = grading_service

    async def start_attempt(self, quiz_id: uuid.UUID, user_id: uuid.UUID) -> AttemptStartResponseDTO:
        """
        Starts a new quiz attempt for a user.

        Args:
            quiz_id: The unique identifier of the quiz.
            user_id: The unique identifier of the user starting the attempt.

        Returns:
            AttemptStartResponseDTO: Information about the newly started attempt.

        Raises:
            NotFoundException: If the quiz is not found or is inactive.
        """
        quiz = await self._quiz_repo.get_by_id(quiz_id)
        if quiz is None or not quiz.is_active:
            raise NotFoundException(f"Quiz {quiz_id} not found or inactive.")
        
        attempt = await self._attempt_repo.create_attempt(quiz_id=quiz.id, user_id=user_id)
        return AttemptStartResponseDTO(
            attempt_id=attempt.id,
            quiz_id=attempt.quiz_id,
            user_id=attempt.user_id,
        )

    async def submit_attempt(
        self,
        attempt_id: uuid.UUID,
        user_id: uuid.UUID,
        request: SubmitAttemptDTO,
    ) -> AttemptResultResponseDTO:
        """
        Submits and grades a quiz attempt, awarding coins and recording results.

        This method orchestrates the grading process, rewards calculation, 
        persists answers, and triggers outbox events for rewards.

        Args:
            attempt_id: The unique identifier of the attempt.
            user_id: The unique identifier of the user submitting the attempt.
            request: The submission payload containing user answers.

        Returns:
            AttemptResultResponseDTO: The final score and reward details.

        Raises:
            NotFoundException: If the attempt is not found or belongs to another user.
            AttemptAlreadyCompletedException: If the attempt has already been submitted.
        """
        attempt = await self._validate_attempt_for_submission(attempt_id, user_id)

        # 1. Grade all provided answers
        graded_results = await self._grade_answers(request.answers)
        
        # 2. Identify and process new rewards
        correct_ids = [qid for qid, _, correct in graded_results if correct]
        newly_rewarded_ids = await self._process_rewards(user_id, attempt.quiz_id, attempt_id, correct_ids)
        
        coins_awarded = len(newly_rewarded_ids) * project_settings.quiz_coins_per_correct_answer

        # 3. Persist answers and finish attempt
        await self._attempt_repo.bulk_save_answers(attempt_id, graded_results)
        
        score = sum(1 for _, _, c in graded_results if c)
        total = len(graded_results)
        await self._attempt_repo.complete_attempt(attempt_id, score=score, total=total)

        logger.info(
            "Attempt submitted", 
            attempt_id=str(attempt_id), 
            score=score, 
            total=total, 
            coins_awarded=coins_awarded
        )

        return AttemptResultResponseDTO(
            attempt_id=attempt_id,
            score=score,
            total_questions=total,
            coins_awarded=coins_awarded,
            question_results=[
                QuestionResultItemDTO(
                    question_id=qid,
                    is_correct=is_correct,
                    was_already_rewarded=qid not in newly_rewarded_ids and is_correct,
                )
                for qid, _, is_correct in graded_results
            ],
        )

    async def _validate_attempt_for_submission(self, attempt_id: uuid.UUID, user_id: uuid.UUID):
        """Validates that an attempt exists, belongs to the user, and is not yet completed."""
        attempt = await self._attempt_repo.get_by_id(attempt_id)
        if attempt is None or attempt.user_id != user_id:
            raise NotFoundException(f"Attempt {attempt_id} not found.")
        
        if attempt.status == AttemptStatusEnum.COMPLETED:
            raise AttemptAlreadyCompletedException(f"Attempt {attempt_id} is already completed.")
        
        return attempt

    async def _grade_answers(self, user_answers: list[AnswerItemDTO]) -> list[tuple[uuid.UUID, dict, bool]]:
        """Grades each user answer against the question definitions."""
        question_ids = [a.question_id for a in user_answers]
        questions = await self._quiz_repo.get_questions_by_ids(question_ids)
        question_map = {q.id: q for q in questions}

        graded: list[tuple[uuid.UUID, dict, bool]] = []
        for ans in user_answers:
            question = question_map.get(ans.question_id)
            if question is None:
                continue
            is_correct = self._grading.check_answer(question, ans.answer_payload)
            graded.append((ans.question_id, ans.answer_payload, is_correct))
        
        return graded

    async def _process_rewards(
        self, 
        user_id: uuid.UUID, 
        quiz_id: uuid.UUID, 
        attempt_id: uuid.UUID, 
        correct_ids: list[uuid.UUID]
    ) -> list[uuid.UUID]:
        """Calculates rewards for correct answers and triggers outbox events."""
        if not correct_ids:
            return []

        already_rewarded = await self._attempt_repo.get_already_rewarded_question_ids(
            user_id=user_id, question_ids=correct_ids
        )
        newly_rewarded_ids = [qid for qid in correct_ids if qid not in already_rewarded]
        
        if not newly_rewarded_ids:
            return []

        await self._attempt_repo.bulk_insert_rewarded_questions(
            user_id=user_id, question_ids=newly_rewarded_ids
        )
        
        coins_to_award = len(newly_rewarded_ids) * project_settings.quiz_coins_per_correct_answer
        
        # Trigger outbox event for the coins reward
        event = QuizRewardEvent(
            payload=QuizRewardPayload(
                user_id=user_id,
                quiz_id=quiz_id,
                attempt_id=attempt_id,
                newly_rewarded_question_ids=newly_rewarded_ids,
                coins_to_award=coins_to_award,
            )
        )
        await self._outbox_repo.insert_event(
            event_id=event.event_id,
            event_type=event.event_type,
            routing_key=project_settings.quiz_reward_routing_key,
            payload=event.model_dump(mode="json"),
        )
        
        return newly_rewarded_ids
