from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Sequence

from src.uow import IUnitOfWork

from src.attempt.enum import AttemptStatusEnum
from src.attempt.entities import QuizAttemptEntity, UserQuestionAnswerEntity
from src.attempt.dependencies.grading_service import IGradingService
from src.attempt.dependencies.reward_service import IRewardService
from src.attempt.dto import (
    AttemptStartResponseDTO,
    AttemptResultResponseDTO,
    QuestionResultItemDTO,
    SubmitAttemptDTO,
    AutoSaveRequestDTO,
)

from src.quiz.entities import QuestionEntity

from src.config.project import settings as project_settings

from shared.exceptions import (
    AttemptAlreadyCompletedException,
    NotFoundException,
    ValidationException,
    ForbiddenException,
)


class AttemptService:
    """Orchestrates the lifecycle of quiz attempts, auto-saving, and submissions."""

    def __init__(
            self,
            uow: IUnitOfWork,
            reward_service: IRewardService,
            grading_service: IGradingService,
    ) -> None:
        """
        Initializes the service with Unit of Work and domain services.

        Args:
            uow: Database Unit of Work instance.
            reward_service: Service for processing coin rewards.
            grading_service: Service for grading strict answer payloads.
        """
        self._uow = uow
        self._rewards = reward_service
        self._grading = grading_service

    async def start_attempt(self, quiz_id: uuid.UUID, user_id: uuid.UUID) -> AttemptStartResponseDTO:
        """
        Initializes a new quiz attempt.

        Args:
            quiz_id: ID of the quiz to start.
            user_id: ID of the user starting the attempt.

        Returns:
            Initial metadata for the attempt.
        """
        async with self._uow:
            quiz = await self._uow.quizzes.get_by_id(quiz_id)
            if quiz is None or not quiz.is_active:
                raise NotFoundException(f"Quiz {quiz_id} not found or inactive.")

            now = datetime.now(tz=timezone.utc)
            attempt_entity = QuizAttemptEntity(
                id=uuid.uuid4(),
                quiz_id=quiz.id,
                user_id=user_id,
                status=AttemptStatusEnum.IN_PROGRESS,
                score=None,
                total_questions=None,
                started_at=now,
                updated_at=now,
                completed_at=None,
            )

            await self._uow.quiz_attempts.add(attempt_entity)
            await self._uow.commit()

            return AttemptStartResponseDTO(
                attempt_id=attempt_entity.id,
                quiz_id=attempt_entity.quiz_id,
                user_id=attempt_entity.user_id,
            )

    async def auto_save_answer(
            self, attempt_id: uuid.UUID, user_id: uuid.UUID, request: AutoSaveRequestDTO
    ) -> None:
        """
        Upserts a single draft answer and updates the attempt's activity timestamp.

        Args:
            attempt_id: ID of the attempt.
            user_id: ID of the requesting user.
            request: DTO containing the single answer payload.
        """
        async with self._uow:
            attempt = await self._uow.quiz_attempts.get_by_id_for_update(attempt_id)
            self._validate_attempt_access(attempt, user_id, attempt_id)

            now = datetime.now(tz=timezone.utc)
            attempt.updated_at = now
            await self._uow.quiz_attempts.update(attempt)

            answer_entity = UserQuestionAnswerEntity(
                id=uuid.uuid4(),
                attempt_id=attempt.id,
                question_id=request.answer.question_id,
                answer_payload=request.answer.answer_payload.model_dump(mode="json"),
                is_correct=None,
                answered_at=now,
            )

            await self._uow.user_answers.upsert_draft(answer_entity)
            await self._uow.commit()

    async def abandon_attempt(self, attempt_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """
        Explicitly marks an active attempt as abandoned.

        Args:
            attempt_id: ID of the attempt.
            user_id: ID of the requesting user.
        """
        async with self._uow:
            attempt = await self._uow.quiz_attempts.get_by_id_for_update(attempt_id)
            self._validate_attempt_access(attempt, user_id, attempt_id)

            attempt.status = AttemptStatusEnum.ABANDONED
            attempt.updated_at = datetime.now(tz=timezone.utc)

            await self._uow.quiz_attempts.update(attempt)
            await self._uow.commit()

    async def submit_attempt(
            self, attempt_id: uuid.UUID, user_id: uuid.UUID, request: SubmitAttemptDTO
    ) -> AttemptResultResponseDTO:
        """
        Finalizes an attempt, grades answers, and processes financial rewards.

        Args:
            attempt_id: ID of the attempt.
            user_id: ID of the user submitting.
            request: DTO containing strictly typed user answers.

        Returns:
            Final score and reward breakdown.
        """
        async with self._uow:
            attempt = await self._uow.quiz_attempts.get_by_id_for_update(attempt_id)
            self._validate_attempt_access(attempt, user_id, attempt_id)

            question_ids = [ans.question_id for ans in request.answers]
            questions = await self._uow.quizzes.get_questions_by_ids(question_ids)

            graded_entities = self._grade_answers(attempt_id, request, questions)

            score = sum(1 for ans in graded_entities if ans.is_correct)
            total = len(graded_entities)

            now = datetime.now(tz=timezone.utc)
            attempt.status = AttemptStatusEnum.COMPLETED
            attempt.score = score
            attempt.total_questions = total
            attempt.updated_at = now
            attempt.completed_at = now

            await self._uow.user_answers.bulk_add(graded_entities)
            await self._uow.quiz_attempts.update(attempt)

            correct_ids = [ans.question_id for ans in graded_entities if ans.is_correct]
            newly_rewarded_ids = await self._rewards.process_rewards(
                user_id=user_id,
                quiz_id=attempt.quiz_id,
                attempt_id=attempt_id,
                correct_question_ids=correct_ids,
            )

            await self._uow.commit()

            return AttemptResultResponseDTO(
                attempt_id=attempt_id,
                score=score,
                total_questions=total,
                coins_awarded=len(newly_rewarded_ids) * project_settings.quiz_coins_per_correct_answer,
                question_results=[
                    QuestionResultItemDTO(
                        question_id=ans.question_id,
                        is_correct=ans.is_correct,
                        was_already_rewarded=ans.question_id not in newly_rewarded_ids and ans.is_correct,
                    )
                    for ans in graded_entities
                ],
            )

    @staticmethod
    def _validate_attempt_access(
            attempt: QuizAttemptEntity | None, user_id: uuid.UUID, attempt_id: uuid.UUID
    ) -> None:
        """Validates existence, ownership, and state of an attempt."""
        if attempt is None:
            raise NotFoundException(f"Attempt {attempt_id} not found.")
        if attempt.user_id != user_id:
            raise ForbiddenException("You do not have permission to modify this attempt.")
        if attempt.status != AttemptStatusEnum.IN_PROGRESS:
            raise AttemptAlreadyCompletedException(f"Attempt {attempt_id} is no longer in progress.")

    def _grade_answers(
            self, attempt_id: uuid.UUID, request: SubmitAttemptDTO, questions: Sequence[QuestionEntity]
    ) -> list[UserQuestionAnswerEntity]:
        """Maps DTOs to Question entities, grades them, and returns Domain Entities."""
        question_map = {q.id: q for q in questions}
        submitted_ids = {ans.question_id for ans in request.answers}

        if len(question_map) != len(submitted_ids):
            missing = submitted_ids - set(question_map.keys())
            raise ValidationException(f"Invalid question IDs in submission: {missing}")

        now = datetime.now(tz=timezone.utc)
        graded_entities: list[UserQuestionAnswerEntity] = []

        for ans_dto in request.answers:
            question = question_map[ans_dto.question_id]
            is_correct = self._grading.check_answer(question, ans_dto.answer_payload)

            graded_entities.append(
                UserQuestionAnswerEntity(
                    id=uuid.uuid4(),
                    attempt_id=attempt_id,
                    question_id=ans_dto.question_id,
                    answer_payload=ans_dto.answer_payload.model_dump(mode="json"),
                    is_correct=is_correct,
                    answered_at=now,
                )
            )

        return graded_entities