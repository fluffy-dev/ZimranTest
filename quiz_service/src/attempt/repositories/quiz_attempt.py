from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.attempt.models.quiz_attempt import QuizAttempt
from src.attempt.enum import AttemptStatusEnum


class QuizAttemptRepository:
    """Repository for managing QuizAttempt entities."""

    def __init__(self, session: AsyncSession) -> None:
        """
        Initializes the repository with a database session.

        Args:
            session: The SQLAlchemy asynchronous session.
        """
        self._session = session

    async def create(self, attempt: QuizAttempt) -> QuizAttempt:
        """
        Persists a new quiz attempt to the database.

        Args:
            attempt: The QuizAttempt model instance to save.

        Returns:
            The persisted QuizAttempt instance.
        """
        self._session.add(attempt)
        await self._session.flush()
        return attempt

    async def get_by_id(self, attempt_id: uuid.UUID) -> QuizAttempt | None:
        """
        Retrieves a quiz attempt by its unique identifier.

        Args:
            attempt_id: The UUID of the attempt.

        Returns:
            The QuizAttempt instance if found, otherwise None.
        """
        result = await self._session.execute(
            select(QuizAttempt).where(QuizAttempt.id == attempt_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_for_update(self, attempt_id: uuid.UUID) -> QuizAttempt | None:
        """
        Retrieves a quiz attempt with a pessimistic lock for updates.

        Args:
            attempt_id: The UUID of the attempt.

        Returns:
            The locked QuizAttempt instance if found, otherwise None.
        """
        result = await self._session.execute(
            select(QuizAttempt)
            .where(QuizAttempt.id == attempt_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def update_status_and_score(
        self,
        attempt_id: uuid.UUID,
        status: AttemptStatusEnum,
        score: int,
        total_questions: int,
        completed_at: datetime,
    ) -> None:
        """
        Updates the completion details of a quiz attempt.

        Args:
            attempt_id: The UUID of the attempt.
            status: The new status of the attempt.
            score: The calculated score.
            total_questions: The total number of questions.
            completed_at: The timestamp of completion.
        """
        await self._session.execute(
            update(QuizAttempt)
            .where(QuizAttempt.id == attempt_id)
            .values(
                status=status,
                score=score,
                total_questions=total_questions,
                completed_at=completed_at,
            )
        )