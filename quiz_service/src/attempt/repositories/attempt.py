from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.attempt.enum import AttemptStatusEnum
from src.config.database.session import ISession
from src.attempt.models.attempt import QuizAttempt, UserQuestionAnswer, UserRewardedQuestion
from src.attempt.entities import QuizAttemptEntity
from shared.logging import get_logger

logger = get_logger(__name__)


def _map_attempt_entity(attempt: QuizAttempt) -> QuizAttemptEntity:
    """Helper to map a QuizAttempt model to a QuizAttemptEntity."""
    return QuizAttemptEntity(
        id=attempt.id,
        quiz_id=attempt.quiz_id,
        user_id=attempt.user_id,
        status=attempt.status,
        score=attempt.score,
        total_questions=attempt.total_questions,
        started_at=attempt.started_at,
        completed_at=attempt.completed_at,
    )


class AttemptRepository:
    """Data access layer for quiz attempts.
    
    Handles the persistence of quiz attempts, user answers, and rewards.
    """

    def __init__(self, session: ISession) -> None:
        """Initializes the repository with a database session.

        Args:
            session: SQLAlchemy async session.
        """
        self._session = session

    async def create_attempt(self, quiz_id: uuid.UUID, user_id: uuid.UUID) -> QuizAttemptEntity:
        """Creates a new quiz attempt record.

        Args:
            quiz_id: ID of the quiz being attempted.
            user_id: ID of the user participating.

        Returns:
            QuizAttemptEntity: Domain representation of the created attempt.
        """
        attempt = QuizAttempt(quiz_id=quiz_id, user_id=user_id)
        self._session.add(attempt)
        await self._session.flush()
        await self._session.refresh(attempt)
        logger.info("Quiz attempt created", attempt_id=str(attempt.id))
        return _map_attempt_entity(attempt)

    async def get_by_id(self, attempt_id: uuid.UUID) -> QuizAttemptEntity | None:
        """Retrieves a quiz attempt by its ID.

        Args:
            attempt_id: Unique identifier for the attempt.

        Returns:
            QuizAttemptEntity | None: The found entity or None.
        """
        result = await self._session.execute(
            select(QuizAttempt)
            .where(QuizAttempt.id == attempt_id)
            .options(selectinload(QuizAttempt.answers))
        )
        attempt = result.scalar_one_or_none()
        return _map_attempt_entity(attempt) if attempt else None

    async def get_by_id_for_update(self, attempt_id: uuid.UUID) -> QuizAttemptEntity | None:
        """Retrieves a quiz attempt with a pessimistic lock.

        Args:
            attempt_id: Unique identifier for the attempt.

        Returns:
            QuizAttemptEntity | None: The locked entity or None.
        """
        result = await self._session.execute(
            select(QuizAttempt)
            .where(QuizAttempt.id == attempt_id)
            .with_for_update()
        )
        attempt = result.scalar_one_or_none()
        return _map_attempt_entity(attempt) if attempt else None

    async def bulk_save_answers(
        self, attempt_id: uuid.UUID, answers: list[tuple[uuid.UUID, dict, bool]]
    ) -> None:
        """Saves multiple user answers within an attempt.

        Args:
            attempt_id: ID of the attempt.
            answers: List of (question_id, payload, is_correct) tuples.
        """
        db_answers = [
            UserQuestionAnswer(
                attempt_id=attempt_id,
                question_id=qid,
                answer_payload=payload,
                is_correct=is_correct,
            )
            for qid, payload, is_correct in answers
        ]
        self._session.add_all(db_answers)

    async def complete_attempt(
        self, attempt_id: uuid.UUID, score: int, total: int
    ) -> QuizAttemptEntity:
        """Finalizes an attempt with score and status update.

        Args:
            attempt_id: ID of the attempt.
            score: Number of correct answers.
            total: Total number of questions.

        Returns:
            QuizAttemptEntity: The updated attempt entity.
        """
        result = await self._session.execute(select(QuizAttempt).where(QuizAttempt.id == attempt_id))
        attempt = result.scalar_one()
        attempt.status = AttemptStatusEnum.COMPLETED
        attempt.score = score
        attempt.total_questions = total
        attempt.completed_at = datetime.now(tz=timezone.utc)
        return _map_attempt_entity(attempt)

    async def get_rewarded_question_ids(self, user_id: uuid.UUID, quiz_id: uuid.UUID) -> set[uuid.UUID]:
        """Retrieves IDs of questions for which the user has already been rewarded.

        Args:
            user_id: ID of the user.
            quiz_id: ID of the quiz.

        Returns:
            set[uuid.UUID]: Set of already rewarded question IDs.
        """
        result = await self._session.execute(
            select(UserRewardedQuestion.question_id)
            .join(QuizAttempt, QuizAttempt.id == UserRewardedQuestion.attempt_id)
            .where(
                UserRewardedQuestion.user_id == user_id,
                QuizAttempt.quiz_id == quiz_id,
            )
        )
        return {row[0] for row in result.all()}

    async def record_rewards(
        self, user_id: uuid.UUID, quiz_id: uuid.UUID, question_ids: list[uuid.UUID]
    ) -> None:
        """Marks specific questions as rewarded for a user.

        Args:
            user_id: ID of the user.
            quiz_id: ID of the quiz (present via attempt context or stored direct).
            question_ids: List of question IDs to reward.
        """
        if not question_ids:
            return
            
        reward_records = [
            UserRewardedQuestion(user_id=user_id, question_id=qid)
            for qid in question_ids
        ]
        self._session.add_all(reward_records)
