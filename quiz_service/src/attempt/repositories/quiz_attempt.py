from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.attempt.models.quiz_attempt import QuizAttempt
from src.attempt.entities import QuizAttemptEntity
from src.attempt.enum import AttemptStatusEnum


class QuizAttemptRepository:
    """Repository for managing QuizAttempt domain entities."""

    def __init__(self, session: AsyncSession) -> None:
        """
        Initializes the repository with a database session.

        Args:
            session: The SQLAlchemy asynchronous session.
        """
        self._session = session

    def _map_to_entity(self, model: QuizAttempt) -> QuizAttemptEntity:
        return QuizAttemptEntity(
            id=model.id,
            quiz_id=model.quiz_id,
            user_id=model.user_id,
            status=model.status,
            score=model.score,
            total_questions=model.total_questions,
            started_at=model.started_at,
            updated_at=model.updated_at,
            completed_at=model.completed_at,
        )

    async def add(self, entity: QuizAttemptEntity) -> None:
        """
        Translates a domain entity into an ORM model and stages it for insertion.

        Args:
            entity: The QuizAttemptEntity to persist.
        """
        model = QuizAttempt(
            id=entity.id,
            quiz_id=entity.quiz_id,
            user_id=entity.user_id,
            status=entity.status,
            score=entity.score,
            total_questions=entity.total_questions,
            started_at=entity.started_at,
            updated_at=entity.updated_at,
            completed_at=entity.completed_at,
        )
        self._session.add(model)

    async def get_by_id(self, attempt_id: uuid.UUID) -> QuizAttemptEntity | None:
        """
        Retrieves an attempt by its ID and maps it to a domain entity.

        Args:
            attempt_id: The UUID of the attempt.

        Returns:
            The mapped QuizAttemptEntity if found, otherwise None.
        """
        result = await self._session.execute(
            select(QuizAttempt).where(QuizAttempt.id == attempt_id)
        )
        model = result.scalar_one_or_none()
        return self._map_to_entity(model) if model else None

    async def get_by_id_for_update(self, attempt_id: uuid.UUID) -> QuizAttemptEntity | None:
        """
        Retrieves a locked attempt by its ID and maps it to a domain entity.

        Args:
            attempt_id: The UUID of the attempt.

        Returns:
            The locked and mapped QuizAttemptEntity if found, otherwise None.
        """
        result = await self._session.execute(
            select(QuizAttempt).where(QuizAttempt.id == attempt_id).with_for_update()
        )
        model = result.scalar_one_or_none()
        return self._map_to_entity(model) if model else None

    async def update(self, entity: QuizAttemptEntity) -> None:
        """
        Updates an existing attempt record based on the provided entity state.

        Args:
            entity: The updated QuizAttemptEntity.
        """
        await self._session.execute(
            update(QuizAttempt)
            .where(QuizAttempt.id == entity.id)
            .values(
                status=entity.status,
                score=entity.score,
                total_questions=entity.total_questions,
                updated_at=entity.updated_at,
                completed_at=entity.completed_at,
            )
        )

    async def mark_abandoned(self, attempt_id: uuid.UUID) -> None:
        """
        Directly updates a specific attempt's status to abandoned.

        Args:
            attempt_id: The UUID of the attempt.
        """
        await self._session.execute(
            update(QuizAttempt)
            .where(QuizAttempt.id == attempt_id)
            .values(status=AttemptStatusEnum.ABANDONED)
        )

    async def bulk_mark_abandoned(self, expiration_threshold: datetime) -> int:
        """
        Bulk updates stalled 'in_progress' attempts to 'abandoned' based on inactivity.

        Args:
            expiration_threshold: The timestamp threshold for inactivity.

        Returns:
            The number of records updated.
        """
        result = await self._session.execute(
            update(QuizAttempt)
            .where(
                QuizAttempt.status == AttemptStatusEnum.IN_PROGRESS,
                QuizAttempt.updated_at < expiration_threshold,
            )
            .values(status=AttemptStatusEnum.ABANDONED)
        )
        return result.rowcount