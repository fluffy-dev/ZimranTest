from __future__ import annotations

import asyncio
import json

import redis.asyncio as aioredis

from src.config.redis import settings as redis_settings
from src.config.rabbitmq import settings as rmq_settings
from src.config.outbox import settings as outbox_settings
from src.config.database.session import AsyncSessionFactory
from src.attempt.repositories.outbox import OutboxRepository
from shared.logging import get_logger
from shared.messaging import MessagePublisher
from shared.messaging.rabbitmq import RabbitMQPublisher

logger = get_logger(__name__)

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

    logger.info("Outbox poller started", interval=outbox_settings.poll_interval)

    while True:
        try:
            async with AsyncSessionFactory() as session:
                repo = OutboxRepository(session)
                events = await repo.get_pending_events(batch_size=outbox_settings.batch_size)

                for event in events:
                    try:
                        body = json.dumps(event.payload).encode()
                        await _publisher.publish(
                            routing_key=event.routing_key,
                            body=body,
                            message_id=str(event.id),
                        )
                        await repo.mark_published(event.id)
                        await session.commit()
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
                        await session.commit()

        except asyncio.CancelledError:
            logger.info("Outbox poller shutting down")
            return
        except Exception as exc:
            logger.error("Outbox poller iteration error", error=str(exc))

        await asyncio.sleep(outbox_settings.poll_interval)


async def startup() -> None:
    """Initializes external connections and starts background services.
    
    Sets up Redis, RabbitMQ, and the outbox poller.
    """
    global redis_client, _publisher, _outbox_task

    # Redis
    redis_client = aioredis.from_url(
        redis_settings.url, encoding="utf-8", decode_responses=True
    )
    await redis_client.ping()
    logger.info("Redis connected", url=redis_settings.url)

    # Publisher — swap class here to change broker
    _publisher = RabbitMQPublisher(
        url=rmq_settings.url,
        exchange_name=rmq_settings.exchange,
    )
    await _publisher.connect()

    # Start outbox poller background task
    _outbox_task = asyncio.create_task(_run_outbox_poller())


async def shutdown() -> None:
    """Closes all background tasks and connections gracefully."""
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
