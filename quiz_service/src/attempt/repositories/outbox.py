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
    """Handles Transactional Outbox event persistence returning pure domain entities."""

    def __init__(self, session: ISession) -> None:
        self._session = session

    async def insert_event(
        self,
        event_id: uuid.UUID,
        event_type: str,
        routing_key: str,
        payload: dict[str, Any],
    ) -> OutboxEventEntity:
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
        result = await self._session.execute(
            select(OutboxEvent)
            .where(OutboxEvent.published_at.is_(None))
            .order_by(OutboxEvent.created_at.asc())
            .limit(batch_size)
        )
        return [_map_outbox_event(e) for e in result.scalars().all()]

    async def mark_published(self, event_id: uuid.UUID) -> None:
        from datetime import datetime, timezone
        await self._session.execute(
            update(OutboxEvent)
            .where(OutboxEvent.id == event_id)
            .values(published_at=datetime.now(tz=timezone.utc))
        )
        await self._session.commit()

    async def increment_attempts(self, event_id: uuid.UUID) -> None:
        await self._session.execute(
            update(OutboxEvent)
            .where(OutboxEvent.id == event_id)
            .values(attempts=OutboxEvent.attempts + 1)
        )
        await self._session.commit()
