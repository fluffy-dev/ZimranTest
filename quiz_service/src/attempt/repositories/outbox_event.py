from __future__ import annotations

import uuid
from datetime import datetime
from typing import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.attempt.models.outbox_event import OutboxEvent
from src.attempt.entities import OutboxEventEntity


class OutboxEventRepository:
    """Repository for managing OutboxEvent domain entities."""

    def __init__(self, session: AsyncSession) -> None:
        """
        Initializes the repository with a database session.

        Args:
            session: The SQLAlchemy asynchronous session.
        """
        self._session = session

    async def add(self, entity: OutboxEventEntity) -> None:
        """
        Translates a domain entity into an ORM model and stages it for insertion.

        Args:
            entity: The OutboxEventEntity to persist.
        """
        model = OutboxEvent(
            id=entity.id,
            event_type=entity.event_type,
            routing_key=entity.routing_key,
            payload=entity.payload,
            created_at=entity.created_at,
            published_at=entity.published_at,
            attempts=entity.attempts,
        )
        self._session.add(model)

    async def get_pending_events(self, batch_size: int) -> Sequence[OutboxEventEntity]:
        """
        Retrieves a locked batch of pending events and maps them to domain entities.

        Args:
            batch_size: Maximum number of events to fetch.

        Returns:
            A sequence of OutboxEventEntity objects ready for processing.
        """
        result = await self._session.execute(
            select(OutboxEvent)
            .where(OutboxEvent.published_at.is_(None))
            .order_by(OutboxEvent.created_at.asc())
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        models = result.scalars().all()

        return [
            OutboxEventEntity(
                id=model.id,
                event_type=model.event_type,
                routing_key=model.routing_key,
                payload=model.payload,
                created_at=model.created_at,
                published_at=model.published_at,
                attempts=model.attempts,
            )
            for model in models
        ]

    async def mark_published(self, entity: OutboxEventEntity) -> None:
        """
        Updates the publication timestamp of an event based on the entity state.

        Args:
            entity: The OutboxEventEntity containing the updated published_at state.
        """
        await self._session.execute(
            update(OutboxEvent)
            .where(OutboxEvent.id == entity.id)
            .values(published_at=entity.published_at)
        )

    async def increment_attempts(self, entity: OutboxEventEntity) -> None:
        """
        Increments the delivery attempt counter for a specific event.

        Args:
            entity: The OutboxEventEntity that failed to publish.
        """
        await self._session.execute(
            update(OutboxEvent)
            .where(OutboxEvent.id == entity.id)
            .values(attempts=OutboxEvent.attempts + 1)
        )