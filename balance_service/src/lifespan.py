from __future__ import annotations

import asyncio

from src.config.rabbitmq import settings as rmq_settings
from src.balance.consumer import handle_quiz_reward_message, start_consumer
from shared.logging import get_logger

logger = get_logger(__name__)

_consumer = None
_consumer_task = None


async def startup() -> None:
    """Initialise all background services required by the application.

    Called once during the FastAPI lifespan ``startup`` phase (before the
    server begins accepting requests). Currently:

    1. Creates and connects the RabbitMQ consumer via
       :func:`~src.balance.consumer.start_consumer`.
    2. Schedules the consumer's message-processing loop as an
       :class:`asyncio.Task` so it runs concurrently with request handling.

    The consumer and task handles are stored in module-level globals so that
    :func:`shutdown` can cancel and close them cleanly.
    """
    global _consumer, _consumer_task

    _consumer = await start_consumer()
    _consumer_task = asyncio.create_task(
        _consumer.consume(handle_quiz_reward_message)
    )
    _consumer_task.add_done_callback(_on_consumer_done)
    logger.info("RabbitMQ consumer started", queue=rmq_settings.queue)


def _on_consumer_done(task: asyncio.Task) -> None:
    """Callback triggered if the consumer task finishes (usually an error)."""
    try:
        task.result()
    except asyncio.CancelledError:
        logger.info("Consumer task cancelled")
    except Exception as exc:
        logger.exception("Consumer task failed unexpectedly", error=str(exc))


async def shutdown() -> None:
    """Gracefully stop all background services during application teardown.

    Called once during the FastAPI lifespan ``shutdown`` phase (after the
    server has stopped accepting new requests). Performs the following steps
    in order:

    1. Cancels the consumer asyncio task and awaits its cancellation so that
       any in-flight ``CancelledError`` is suppressed cleanly.
    2. Closes the underlying AMQP connection, flushing any pending
       acknowledgements.

    Both steps are guarded by ``None`` checks, so this function is safe to
    call even if :func:`startup` was never completed (e.g. during tests).
    """
    global _consumer, _consumer_task

    if _consumer_task:
        _consumer_task.cancel()
        try:
            await _consumer_task
        except asyncio.CancelledError:
            pass

    if _consumer:
        await _consumer.close()
