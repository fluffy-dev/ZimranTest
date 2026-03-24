from __future__ import annotations

import asyncio
import json

import redis.asyncio as aioredis

from src.config.redis import settings as redis_settings
from src.config.rabbitmq import settings as rmq_settings
from src.config.outbox import settings as outbox_settings
from src.uow import SqlAlchemyUnitOfWork
from src.attempt.entities import OutboxEventEntity
from shared.logging import get_logger
from shared.messaging import MessagePublisher
from shared.messaging.rabbitmq import RabbitMQPublisher

logger = get_logger(__name__)

# Module-level singletons (set during lifespan)
redis_client: aioredis.Redis | None = None
_publisher: MessagePublisher | None = None
_outbox_task: asyncio.Task | None = None


async def _publish_outbox_event(
    uow: SqlAlchemyUnitOfWork,
    event: OutboxEventEntity,
    publisher: MessagePublisher,
) -> None:
    """
    Serializes and publishes a single event to the message broker.
    Marks the event as published on success, or increments attempts on failure.
    """
    try:
        body = json.dumps(event.payload).encode()
        await publisher.publish(
            routing_key=event.routing_key,
            body=body,
            message_id=str(event.id),
        )
        await uow.outbox.mark_published(event.id)
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
        await uow.outbox.increment_attempts(event.id)


async def _process_pending_outbox_events(publisher: MessagePublisher) -> None:
    """
    Fetches a batch of pending outbox events and processes them one by one.
    Each event is processed in its own transaction (UoW) to ensure reliability.
    """
    async with SqlAlchemyUnitOfWork() as uow:
        events = await uow.outbox.get_pending_events(batch_size=outbox_settings.batch_size)

    for event in events:
        async with SqlAlchemyUnitOfWork() as uow:
            await _publish_outbox_event(uow, event, publisher)
            await uow.commit()


async def _run_outbox_poller() -> None:
    """
    Main loop for the background outbox poller.
    Orchestrates the periodic processing of pending events.
    """
    global _publisher
    assert _publisher is not None

    logger.info("Outbox poller started", interval=outbox_settings.poll_interval)

    while True:
        try:
            await _process_pending_outbox_events(_publisher)
        except asyncio.CancelledError:
            logger.info("Outbox poller shutting down")
            return
        except Exception as exc:
            logger.error("Outbox poller iteration error", error=str(exc))

        await asyncio.sleep(outbox_settings.poll_interval)


async def startup() -> None:
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
