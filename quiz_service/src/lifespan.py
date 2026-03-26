from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone, timedelta
from typing import Optional

import redis.asyncio as aioredis

from src.config.redis import settings as redis_settings
from src.config.rabbitmq import settings as rmq_settings
from src.config.outbox import settings as outbox_settings
from src.config.attempt import settings as attempt_settings
from src.config.database.engine import db_helper
from src.attempt.repositories.outbox_event import OutboxEventRepository
from src.attempt.repositories.quiz_attempt import QuizAttemptRepository
from src.attempt.entities import OutboxEventEntity
from shared.logging import get_logger
from shared.messaging import MessagePublisher
from shared.messaging.rabbitmq import RabbitMQPublisher

logger = get_logger(__name__)

# Global resource holders for dependency injection
redis_client: Optional[aioredis.Redis] = None
_publisher: Optional[MessagePublisher] = None
_outbox_task: Optional[asyncio.Task] = None
_abandonment_task: Optional[asyncio.Task] = None


class AttemptAbandonmentProcessor:
    """
    Periodically checks for and marks stale in-progress attempts as abandoned.
    """

    def __init__(self) -> None:
        self._session_factory = db_helper.session_factory

    async def run(self) -> None:
        logger.info("Attempt abandonment poller starting", interval=attempt_settings.abandon_poll_interval)
        try:
            while True:
                await self._process()
                await asyncio.sleep(attempt_settings.abandon_poll_interval)
        except asyncio.CancelledError:
            logger.info("Attempt abandonment poller task received cancellation signal")
        except Exception as exc:
            logger.exception("Attempt abandonment poller encountered unhandled exception", error=str(exc))

    async def _process(self) -> None:
        try:
            threshold = datetime.now(tz=timezone.utc) - timedelta(minutes=attempt_settings.abandon_timeout_minutes)
            async with self._session_factory() as session:
                repo = QuizAttemptRepository(session)
                count = await repo.bulk_mark_abandoned(threshold)
                await session.commit()
                if count > 0:
                    logger.info("Marked stale attempts as abandoned", count=count)
        except Exception as exc:
            logger.error("Failed to run attempt abandonment job", error=str(exc))


class OutboxProcessor:
    """
    Orchestrates the 'Relay' phase of the Transactional Outbox pattern.

    Processes pending OutboxEvent entities and ensures at-least-once
    delivery to the configured message broker.
    """

    def __init__(self, publisher: MessagePublisher) -> None:
        """
        Initializes the processor with a connected publisher.

        Args:
            publisher: Implementation of the MessagePublisher interface.
        """
        self._publisher = publisher
        self._session_factory = db_helper.session_factory

    async def run(self) -> None:
        """
        The main execution loop for the outbox poller.
        """
        logger.info("Outbox poller starting", interval=outbox_settings.poll_interval)
        try:
            while True:
                processed = await self._process_next_batch()

                # If no events were found, sleep; otherwise, check immediately for next batch
                if processed == 0:
                    await asyncio.sleep(outbox_settings.poll_interval)
        except asyncio.CancelledError:
            logger.info("Outbox poller task received cancellation signal")
        except Exception as exc:
            logger.exception("Outbox poller encountered unhandled exception", error=str(exc))

    async def _process_next_batch(self) -> int:
        """
        Fetches and publishes a single batch of events.

        Returns:
            The number of successfully processed events.
        """
        async with self._session_factory() as session:
            repo = OutboxEventRepository(session)
            events = await repo.get_pending_events(batch_size=outbox_settings.batch_size)

            if not events:
                return 0

            for event in events:
                if not await self._handle_event(repo, event, session):
                    # Broker connection failure: stop batch and wait for reconnect
                    break

            return len(events)

    async def _handle_event(
            self,
            repo: OutboxEventRepository,
            event: OutboxEventEntity,
            session
    ) -> bool:
        """
        Publishes a single event and updates its database status.

        Returns:
            bool: True if iteration should continue, False on broker failure.
        """
        try:
            # Serialize the dict payload to bytes for the broker
            payload_bytes = json.dumps(event.payload).encode()

            await self._publisher.publish(
                routing_key=event.routing_key,
                body=payload_bytes,
                message_id=str(event.id),
            )

            # Update entity state and persist via repository
            event.published_at = datetime.now(tz=timezone.utc)
            await repo.mark_published(event)
            await session.commit()

            logger.info("Outbox event published", event_id=str(event.id), type=event.event_type)
            return True

        except (ConnectionError, TimeoutError) as net_err:
            logger.error("Message broker unreachable", error=str(net_err))
            await session.rollback()
            return False

        except Exception as exc:
            logger.error("Failed to process outbox event", event_id=str(event.id), error=str(exc))
            await repo.increment_attempts(event)
            await session.commit()
            return True


async def startup() -> None:
    """
    Bootstraps the application's external dependencies and background tasks.
    """
    global redis_client, _publisher, _outbox_task

    # 1. Initialize Redis
    try:
        redis_client = aioredis.from_url(
            redis_settings.url,
            encoding="utf-8",
            decode_responses=True
        )
        await redis_client.ping()
        logger.info("Redis connection established")
    except Exception as exc:
        logger.critical("Failed to connect to Redis", error=str(exc))
        raise

    # 2. Initialize RabbitMQ Publisher
    try:
        _publisher = RabbitMQPublisher(
            url=rmq_settings.url,
            exchange_name=rmq_settings.exchange,
        )
        await _publisher.connect()
        logger.info("RabbitMQ publisher connected")
    except Exception as exc:
        logger.critical("Failed to connect to RabbitMQ", error=str(exc))
        raise

    # 3. Start Outbox Poller
    processor = OutboxProcessor(_publisher)
    _outbox_task = asyncio.create_task(processor.run(), name="outbox_poller")

    # 4. Start Attempt Abandonment Poller
    abandon_processor = AttemptAbandonmentProcessor()
    _abandonment_task = asyncio.create_task(abandon_processor.run(), name="attempt_abandonment_poller")


async def shutdown() -> None:
    """
    Gracefully terminates all background tasks and external connections.
    """
    global redis_client, _publisher, _outbox_task, _abandonment_task

    logger.info("Initiating graceful shutdown")

    if _abandonment_task:
        _abandonment_task.cancel()
        try:
            await _abandonment_task
        except asyncio.CancelledError:
            pass
        logger.info("Attempt abandonment poller task terminated")

    if _outbox_task:
        _outbox_task.cancel()
        try:
            await _outbox_task
        except asyncio.CancelledError:
            pass
        logger.info("Outbox poller task terminated")

    if _publisher:
        await _publisher.close()
        logger.info("RabbitMQ publisher disconnected")

    if redis_client:
        await redis_client.aclose()
        logger.info("Redis connection closed")