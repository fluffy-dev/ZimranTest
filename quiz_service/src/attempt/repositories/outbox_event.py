from __future__ import annotations

import uuid
from datetime import datetime
from typing import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.attempt.models.outbox_event import OutboxEvent


class OutboxEventRepository:
    """Repository for managing OutboxEvent entities."""

    def __init__(self, session: AsyncSession) -> None:
        """
        Initializes the repository with a database session.

        Args:
            session: The SQLAlchemy asynchronous session.
        """
        self._session = session

    async def create(self, event: OutboxEvent) -> None:
        """
        Persists a new outbox event to the database.

        Args:
            event: The OutboxEvent model instance to save.
        """
        self._session.add(event)

    async def get_pending_events(self, batch_size: int) -> Sequence[OutboxEvent]:
        """
        Retrieves a batch of unpublished events with a pessimistic lock.

        Args:
            batch_size: The maximum number of events to retrieve.

        Returns:
            A sequence of pending OutboxEvent instances.
        """
        result = await self._session.execute(
            select(OutboxEvent)
            .where(OutboxEvent.published_at.is_(None))
            .order_by(OutboxEvent.created_at.asc())
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        return result.scalars().all()

    async def mark_published(self, event_id: uuid.UUID, published_at: datetime) -> None:
        """
        Updates an event to indicate it has been successfully published.

        Args:
            event_id: The UUID of the event.
            published_at: The timestamp of publication.
        """
        await self._session.execute(
            update(OutboxEvent)
            .where(OutboxEvent.id == event_id)
            .values(published_at=published_at)
        )

    async def increment_attempts(self, event_id: uuid.UUID) -> None:
        """
        Increments the delivery attempt counter for a specific event.

        Args:
            event_id: The UUID of the event.
        """
        await self._session.execute(
            update(OutboxEvent)
            .where(OutboxEvent.id == event_id)
            .values(attempts=OutboxEvent.attempts + 1)
        )