from __future__ import annotations

import asyncio
import json

import redis.asyncio as aioredis

from app.core.config import settings
from app.db.session import AsyncSessionFactory
from app.repositories.outbox_repository import OutboxRepository
from shared.logging import get_logger
from shared.messaging import MessagePublisher
from shared.messaging.rabbitmq import RabbitMQPublisher

logger = get_logger(__name__)

# Module-level singletons (set during lifespan)
redis_client: aioredis.Redis | None = None
_publisher: MessagePublisher | None = None
_outbox_task: asyncio.Task | None = None


async def _run_outbox_poller() -> None:
    """
    Background task that reads pending outbox events and publishes them to RabbitMQ.
    Runs every OUTBOX_POLL_INTERVAL seconds.

    This implements the Polling Publisher variant of the Transactional Outbox pattern:
    - Atomically written with DB writes
    - Independently published by this background worker
    - Guarantees at-least-once delivery
    - Balance service is idempotent (handles duplicates via idempotency_key)
    """
    global _publisher
    assert _publisher is not None

    logger.info("Outbox poller started", interval=settings.OUTBOX_POLL_INTERVAL)

    while True:
        try:
            async with AsyncSessionFactory() as session:
                repo = OutboxRepository(session)
                events = await repo.get_pending_events(batch_size=settings.OUTBOX_BATCH_SIZE)

                for event in events:
                    try:
                        body = json.dumps(event.payload).encode()
                        await _publisher.publish(
                            routing_key=event.routing_key,
                            body=body,
                            message_id=str(event.id),
                        )
                        await repo.mark_published(event.id)
                        logger.info(
                            "Outbox event published",
                            event_id=str(event.id),
                            event_type=event.event_type,
                        )
                    except Exception as exc:
                        logger.error(
                            "Failed to publish outbox event",
                            event_id=str(event.id),
                            error=str(exc),
                        )
                        await repo.increment_attempts(event.id)

        except asyncio.CancelledError:
            logger.info("Outbox poller shutting down")
            return
        except Exception as exc:
            logger.error("Outbox poller iteration error", error=str(exc))

        await asyncio.sleep(settings.OUTBOX_POLL_INTERVAL)


async def startup() -> None:
    global redis_client, _publisher, _outbox_task

    # Redis
    redis_client = aioredis.from_url(
        settings.REDIS_URL, encoding="utf-8", decode_responses=True
    )
    await redis_client.ping()
    logger.info("Redis connected", url=settings.REDIS_URL)

    # Publisher — swap class here to change broker
    _publisher = RabbitMQPublisher(
        url=settings.RABBITMQ_URL,
        exchange_name=settings.RABBITMQ_EXCHANGE,
    )
    await _publisher.connect()

    # Start outbox poller background task
    _outbox_task = asyncio.create_task(_run_outbox_poller())


async def shutdown() -> None:
    global redis_client, _publisher, _outbox_task

    if _outbox_task:
        _outbox_task.cancel()
        try:
            await _outbox_task
        except asyncio.CancelledError:
            pass

    if _publisher:
        await _publisher.close()

    if redis_client:
        await redis_client.aclose()
        logger.info("Redis disconnected")
