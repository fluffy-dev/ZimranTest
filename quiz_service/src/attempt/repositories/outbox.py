from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.attempt.models.outbox import OutboxEvent


class OutboxRepository:
    """Repository for managing the transactional outbox.
    
    Handles persisting events as part of a business transaction to ensure
    guaranteed delivery to the message broker.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initializes the repository with a database session.

        Args:
            session: SQLAlchemy async session.
        """
        self._session = session

    async def save_event(self, event_type: str, routing_key: str, payload: dict[str, Any]) -> None:
        """Persists a new event to the outbox.

        Args:
            event_type: Type of event (e.g., 'quiz.completed').
            routing_key: Destination routing key for the broker.
            payload: JSON-serializable event data.
        """
        event = OutboxEvent(
            event_type=event_type,
            routing_key=routing_key,
            payload=payload,
        )
        self._session.add(event)

    async def get_pending_events(self, batch_size: int = 10) -> list[OutboxEvent]:
        """Retrieves unpublished events for processing by the poller.

        Args:
            batch_size: Maximum number of events to retrieve.

        Returns:
            list[OutboxEvent]: List of pending events.
        """
        result = await self._session.execute(
            select(OutboxEvent)
            .where(OutboxEvent.processed_at.is_(None))
            .limit(batch_size)
            .order_by(OutboxEvent.created_at.asc())
        )
        return list(result.scalars().all())

    async def mark_published(self, event_id: uuid.UUID) -> None:
        """Marks an event as successfully published.

        Args:
            event_id: Unique identifier for the event.
        """
        from datetime import datetime, timezone
        result = await self._session.execute(select(OutboxEvent).where(OutboxEvent.id == event_id))
        event = result.scalar_one_or_none()
        if event:
            event.processed_at = datetime.now(tz=timezone.utc)

    async def increment_attempts(self, event_id: uuid.UUID) -> None:
        """Increments the delivery attempt counter for a failed event.

        Args:
            event_id: Unique identifier for the event.
        """
        result = await self._session.execute(select(OutboxEvent).where(OutboxEvent.id == event_id))
        event = result.scalar_one_or_none()
        if event:
            event.attempts += 1
