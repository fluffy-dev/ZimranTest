from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, update

from app.db.models import OutboxEvent
from app.dependencies.common import ISession
from shared.logging import get_logger

logger = get_logger(__name__)


class OutboxRepository:
    """Handles Transactional Outbox event persistence and marking as published."""

    def __init__(self, session: ISession) -> None:
        self._session = session

    async def insert_event(
        self,
        event_id: uuid.UUID,
        event_type: str,
        routing_key: str,
        payload: dict[str, Any],
    ) -> OutboxEvent:
        event = OutboxEvent(
            id=event_id,
            event_type=event_type,
            routing_key=routing_key,
            payload=payload,
        )
        self._session.add(event)
        await self._session.flush()
        return event

    async def get_pending_events(self, batch_size: int = 50) -> list[OutboxEvent]:
        """Fetch events not yet published, ordered by creation time (FIFO)."""
        result = await self._session.execute(
            select(OutboxEvent)
            .where(OutboxEvent.published_at.is_(None))
            .order_by(OutboxEvent.created_at.asc())
            .limit(batch_size)
        )
        return list(result.scalars().all())

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
