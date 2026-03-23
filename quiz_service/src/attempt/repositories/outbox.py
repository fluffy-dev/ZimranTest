import uuid
from typing import Any

from sqlalchemy import select, update

from src.attempt.models.attempt import OutboxEvent
from src.attempt.entities import OutboxEventEntity
from src.config.database.session import ISession
from shared.logging import get_logger

logger = get_logger(__name__)


def _map_outbox_event(event: OutboxEvent) -> OutboxEventEntity:
    return OutboxEventEntity(
        id=event.id,
        event_type=event.event_type,
        routing_key=event.routing_key,
        payload=event.payload,
        created_at=event.created_at,
        published_at=event.published_at,
        attempts=event.attempts,
    )


class OutboxRepository:
    """
    Data access layer for Transactional Outbox events.
    Ensures that events are persisted along with business data for reliable delivery.
    """

    def __init__(self, session: ISession) -> None:
        """Initializes the repository with a database session."""
        self._session = session

    async def insert_event(
        self,
        event_id: uuid.UUID,
        event_type: str,
        routing_key: str,
        payload: dict[str, Any],
    ) -> OutboxEventEntity:
        """
        Inserts a new event into the outbox table.

        Args:
            event_id: Unique identifier for the event.
            event_type: Categorization of the event (e.g., 'quiz.rewarded').
            routing_key: The destination topic or queue identifier.
            payload: The actual data content of the event.

        Returns:
            OutboxEventEntity: The persisted event domain entity.
        """
        event = OutboxEvent(
            id=event_id,
            event_type=event_type,
            routing_key=routing_key,
            payload=payload,
        )
        self._session.add(event)
        await self._session.flush()
        return _map_outbox_event(event)

    async def get_pending_events(self, batch_size: int = 50) -> list[OutboxEventEntity]:
        """
        Retrieves events that have not yet been published.

        Args:
            batch_size: Maximum number of events to retrieve in one call.

        Returns:
            list[OutboxEventEntity]: A list of pending event entities.
        """
        result = await self._session.execute(
            select(OutboxEvent)
            .where(OutboxEvent.published_at.is_(None))
            .order_by(OutboxEvent.created_at.asc())
            .limit(batch_size)
        )
        return [_map_outbox_event(e) for e in result.scalars().all()]

    async def mark_published(self, event_id: uuid.UUID) -> None:
        """
        Marks an event as successfully published by setting the 'published_at' timestamp.

        Args:
            event_id: Unique identifier of the event.
        """
        from datetime import datetime, timezone
        await self._session.execute(
            update(OutboxEvent)
            .where(OutboxEvent.id == event_id)
            .values(published_at=datetime.now(tz=timezone.utc))
        )
        await self._session.commit()

    async def increment_attempts(self, event_id: uuid.UUID) -> None:
        """
        Increments the retry counter for a failed event publication attempt.

        Args:
            event_id: Unique identifier of the event.
        """
        await self._session.execute(
            update(OutboxEvent)
            .where(OutboxEvent.id == event_id)
            .values(attempts=OutboxEvent.attempts + 1)
        )
        await self._session.commit()
