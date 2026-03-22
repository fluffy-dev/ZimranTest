from __future__ import annotations

import uuid

from src.quiz.dependencies.repository import IQuizRepository

from src.attempt.models.attempt import AttemptStatus
from src.attempt.dependencies.repository import IAttemptRepository, IOutboxRepository
from src.attempt.dependencies.grading_service import IGradingService
from src.attempt.dto import AttemptResultResponseDTO, QuestionResultItemDTO, SubmitAttemptDTO, AttemptStartResponseDTO

from shared.exceptions import AttemptAlreadyCompletedException, NotFoundException
from shared.logging import get_logger
from shared.schemas import QuizRewardEvent, QuizRewardPayload

logger = get_logger(__name__)

COINS_PER_CORRECT_ANSWER = 100
QUIZ_REWARD_ROUTING_KEY = "quiz.questions.rewarded"


class AttemptService:
    """Orchestrates quiz submission flow utilizing distinct bounded domains."""

    def __init__(
        self,
        attempt_repo: IAttemptRepository,
        quiz_repo: IQuizRepository,
        outbox_repo: IOutboxRepository,
        grading_service: IGradingService,
    ) -> None:
        self._quiz_repo = quiz_repo
        self._attempt_repo = attempt_repo
        self._outbox_repo = outbox_repo
        self._grading = grading_service

    async def start_attempt(self, quiz_id: uuid.UUID, user_id: uuid.UUID) -> AttemptStartResponseDTO:
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
        attempt = await self._attempt_repo.get_by_id(attempt_id)
        if attempt is None or attempt.user_id != user_id:
            raise NotFoundException(f"Attempt {attempt_id} not found.")
        if attempt.status == AttemptStatus.COMPLETED:
            raise AttemptAlreadyCompletedException(f"Attempt {attempt_id} is already completed.")

        question_ids = [a.question_id for a in request.answers]
        questions = await self._quiz_repo.get_questions_by_ids(question_ids)
        question_map = {q.id: q for q in questions}

        graded: list[tuple[uuid.UUID, dict, bool]] = []
        for ans in request.answers:
            question = question_map.get(ans.question_id)
            if question is None:
                continue
            is_correct = self._grading.check_answer(question, ans.answer_payload)
            graded.append((ans.question_id, ans.answer_payload, is_correct))

        correct_ids = [qid for qid, _, correct in graded if correct]
        already_rewarded = await self._attempt_repo.get_already_rewarded_question_ids(
            user_id=user_id, question_ids=correct_ids
        )
        newly_rewarded_ids = [qid for qid in correct_ids if qid not in already_rewarded]
        coins_to_award = len(newly_rewarded_ids) * COINS_PER_CORRECT_ANSWER

        await self._attempt_repo.bulk_save_answers(attempt_id, graded)
        await self._attempt_repo.bulk_insert_rewarded_questions(
            user_id=user_id, question_ids=newly_rewarded_ids
        )
        if coins_to_award > 0:
            event = QuizRewardEvent(
                payload=QuizRewardPayload(
                    user_id=user_id,
                    quiz_id=attempt.quiz_id,
                    attempt_id=attempt_id,
                    newly_rewarded_question_ids=newly_rewarded_ids,
                    coins_to_award=coins_to_award,
                )
            )
            await self._outbox_repo.insert_event(
                event_id=event.event_id,
                event_type=event.event_type,
                routing_key=QUIZ_REWARD_ROUTING_KEY,
                payload=event.model_dump(mode="json"),
            )

        score = sum(1 for _, _, c in graded if c)
        total = len(graded)
        await self._attempt_repo.complete_attempt(attempt_id, score=score, total=total)

        logger.info("Attempt submitted", attempt_id=str(attempt_id), score=score, total=total, coins_awarded=coins_to_award)

        return AttemptResultResponseDTO(
            attempt_id=attempt_id,
            score=score,
            total_questions=total,
            coins_awarded=coins_to_award,
            question_results=[
                QuestionResultItemDTO(
                    question_id=qid,
                    is_correct=is_correct,
                    was_already_rewarded=qid not in newly_rewarded_ids and is_correct,
                )
                for qid, _, is_correct in graded
            ],
        )
