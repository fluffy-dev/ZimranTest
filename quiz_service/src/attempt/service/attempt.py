from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from src.uow import IUnitOfWork
from src.attempt.service.reward import RewardService
from src.attempt.service.grading import GradingService
from src.attempt.enum import AttemptStatusEnum
from src.attempt.entities import AnswerEntity
from src.attempt.dto import (
    AttemptStartResponseDTO, 
    AttemptResultResponseDTO, 
    QuestionResultItemDTO, 
    SubmitAttemptDTO
)
from src.config.project import settings as project_settings
from shared.exceptions import AttemptAlreadyCompletedException, NotFoundException, ValidationException
from shared.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class AttemptService:
    """Orchestrates the lifecycle of a quiz attempt with strict transactional boundaries.
    
    Returns DTOs directly, mirroring the balance_service architectural style.
    """

    def __init__(
        self,
        uow: IUnitOfWork,
        reward_service: RewardService,
    ) -> None:
        """Initializes the service with Unit of Work and Reward service.

        Args:
            uow: Database Unit of Work instance.
            reward_service: Service for processing coin rewards.
        """
        self._uow = uow
        self._rewards = reward_service
        self._grading = GradingService()

    async def start_attempt(self, quiz_id: uuid.UUID, user_id: uuid.UUID) -> AttemptStartResponseDTO:
        """Starts a new quiz attempt.

        Args:
            quiz_id: ID of the quiz to start.
            user_id: ID of the user starting the attempt.

        Returns:
            AttemptStartResponseDTO: Initial metadata for the attempt.
        """
        async with self._uow:

            quiz = await self._uow.quizzes.get_by_id(quiz_id)

            if quiz is None or not quiz.is_active:
                raise NotFoundException(f"Quiz {quiz_id} not found or inactive.")
            
            attempt = await self._uow.attempts.create_attempt(quiz_id=quiz.id, user_id=user_id)

            await self._uow.commit()
            
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
        """Submits and grades a quiz attempt with pessimistic locking.

        Args:
            attempt_id: ID of the attempt being submitted.
            user_id: ID of the user submitting.
            request: DTO containing user answers.

        Returns:
            AttemptResultResponseDTO: Final score and rewards.
        """
        async with self._uow:
            attempt = await self._uow.attempts.get_by_id_for_update(attempt_id)
            
            if attempt is None or attempt.user_id != user_id:
                raise NotFoundException(f"Attempt {attempt_id} not found.")
            
            if attempt.status == AttemptStatusEnum.COMPLETED:
                raise AttemptAlreadyCompletedException(f"Attempt {attempt_id} is already completed.")

            graded_results = await self._grade_answers(request.answers)
            
            score = sum(1 for ans in graded_results if ans.is_correct)
            total = len(graded_results)
            
            await self._uow.attempts.bulk_save_answers(
                attempt_id, 
                [(ans.question_id, ans.answer_payload, ans.is_correct) for ans in graded_results]
            )
            
            await self._uow.attempts.complete_attempt(
                attempt_id, score=score, total=total
            )
            
            correct_ids = [ans.question_id for ans in graded_results if ans.is_correct]
            newly_rewarded_ids = await self._rewards.process_rewards(
                user_id=user_id, 
                quiz_id=attempt.quiz_id, 
                attempt_id=attempt_id, 
                correct_question_ids=correct_ids
            )
            
            await self._uow.commit()
            
            coins_awarded = len(newly_rewarded_ids) * project_settings.quiz_coins_per_correct_answer
            
            logger.info(
                "Attempt finalized", 
                attempt_id=str(attempt_id), 
                score=score, 
                total=total,
                coins=coins_awarded
            )
            
            return AttemptResultResponseDTO(
                attempt_id=attempt_id,
                score=score,
                total_questions=total,
                coins_awarded=coins_awarded,
                question_results=[
                    QuestionResultItemDTO(
                        question_id=ans.question_id,
                        is_correct=ans.is_correct,
                        was_already_rewarded=ans.question_id not in newly_rewarded_ids and ans.is_correct
                    )
                    for ans in graded_results
                ]
            )

    async def _grade_answers(self, user_answers: list[Any]) -> list[AnswerEntity]:
        """Grades provided answers and returns domain entities.

        Args:
            user_answers: Raw answer payloads from the request.

        Returns:
            list[AnswerEntity]: Graded entities ready for persistence.
        """
        question_ids = [a.question_id for a in user_answers]
        questions = await self._uow.quizzes.get_questions_by_ids(question_ids)
        question_map = {q.id: q for q in questions}

        if len(question_map) != len(set(question_ids)):
            missing = set(question_ids) - set(question_map.keys())
            raise ValidationException(f"Invalid question IDs in submission: {missing}")

        graded: list[AnswerEntity] = []
        for ans in user_answers:
            question = question_map[ans.question_id]
            is_correct = self._grading.check_answer(question, ans.answer_payload)
            graded.append(AnswerEntity(
                question_id=ans.question_id,
                answer_payload=ans.answer_payload,
                is_correct=is_correct
            ))
        
        return graded
