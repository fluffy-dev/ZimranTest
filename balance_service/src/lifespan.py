from __future__ import annotations

import asyncio

from src.config.rabbitmq import settings as rmq_settings
from src.balance.consumer import handle_quiz_reward_message, start_consumer
from shared.logging import get_logger

logger = get_logger(__name__)

_consumer = None
_consumer_task = None


async def startup() -> None:
    global _consumer, _consumer_task

    _consumer = await start_consumer()
    _consumer_task = asyncio.create_task(
        _consumer.consume(handle_quiz_reward_message)
    )
    logger.info("RabbitMQ consumer started", queue=rmq_settings.queue)


async def shutdown() -> None:
    global _consumer, _consumer_task

    if _consumer_task:
        _consumer_task.cancel()
        try:
            await _consumer_task
        except asyncio.CancelledError:
            pass

    if _consumer:
        await _consumer.close()
