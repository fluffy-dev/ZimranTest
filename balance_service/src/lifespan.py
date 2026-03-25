from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from fastapi import FastAPI

from src.config.rabbitmq import settings as rmq_settings
from src.balance.consumer import handle_quiz_reward_message, start_consumer
from shared.logging import get_logger
from shared.messaging.base import MessageConsumer

logger = get_logger(__name__)

_consumer: Optional[MessageConsumer] = None
_supervisor_task: Optional[asyncio.Task] = None
MAX_BACKOFF: int = 60


async def _supervise_consumer() -> None:
    """Maintains the consumer connection, retrying infinitely on failure.

    Implements an exponential backoff strategy for reconnections up to a
    maximum delay. Ensures the application resiliently recovers its messaging
    capabilities if the broker becomes temporarily unavailable.
    """
    global _consumer
    retry_count = 0

    while True:
        try:
            if _consumer:
                await _consumer.close()

            _consumer = await start_consumer()
            logger.info("Consumer connected and consuming", attempt=retry_count)
            retry_count = 0

            await _consumer.consume(handle_quiz_reward_message)

        except asyncio.CancelledError:
            logger.info("Consumer supervisor cancelled safely")
            break
        except Exception as exc:
            retry_count += 1
            delay = min(2 ** retry_count, MAX_BACKOFF)
            logger.error(
                "Consumer task failed, scheduling restart",
                error=str(exc),
                delay=delay,
                attempt=retry_count,
            )
            await asyncio.sleep(delay)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages the startup and shutdown lifecycle of background services.

    Replaces legacy startup/shutdown event handlers with the modern FastAPI
    context manager approach. Starts the RabbitMQ consumer supervisor on
    boot and ensures graceful cancellation and connection closure on shutdown.

    Args:
        app: The current FastAPI application instance.

    Yields:
        None, returning control to the ASGI server to accept HTTP requests.
    """
    global _consumer, _supervisor_task

    _supervisor_task = asyncio.create_task(_supervise_consumer())
    logger.info("RabbitMQ consumer supervisor started", queue=rmq_settings.queue)

    yield

    if _supervisor_task:
        _supervisor_task.cancel()
        try:
            await _supervisor_task
        except asyncio.CancelledError:
            pass

    if _consumer:
        await _consumer.close()
        logger.info("RabbitMQ consumer connection closed")


def is_consumer_connected() -> bool:
    """Checks if the RabbitMQ consumer is currently active and connected.

    Returns:
        True if the consumer is instantiated and connected, False otherwise.
    """
    return _consumer is not None and _consumer.is_connected