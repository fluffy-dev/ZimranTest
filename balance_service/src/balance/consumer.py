from __future__ import annotations

import json

from src.config.rabbitmq import settings as rmq_settings
from src.uow import SqlAlchemyUnitOfWork
from src.balance.service.balance import BalanceService
from shared.logging import get_logger
from shared.messaging import MessageConsumer
from shared.messaging.rabbitmq import RabbitMQConsumer
from shared.schemas import QuizRewardEvent

logger = get_logger(__name__)


async def handle_quiz_reward_message(
    body: bytes,
    routing_key: str,
    message_id: str,
) -> None:
    """Process a single ``quiz.questions.rewarded`` RabbitMQ message.

    Creates a fresh Unit of Work for each message, ensuring that the
    balance credit and transaction record are committed atomically.
    Re-raises exceptions so the consumer can nack and route to DLQ.

    Args:
        body: Raw UTF-8-encoded JSON message body from RabbitMQ.
        routing_key: The routing key the message was published with.
        message_id: The AMQP message-id property for correlation.

    Raises:
        Exception: Any error is re-raised for DLQ routing.
    """
    raw = body.decode("utf-8")
    logger.info(
        "Received quiz reward message",
        routing_key=routing_key,
        message_id=message_id,
    )

    try:
        data = json.loads(raw)
        event = QuizRewardEvent.model_validate(data)
    except Exception as exc:
        logger.error("Failed to deserialize quiz reward event", error=str(exc), raw=raw[:300])
        raise

    uow = SqlAlchemyUnitOfWork()
    service = BalanceService(uow)
    balance = await service.credit_from_quiz_event(event)
    logger.info(
        "Balance credited from quiz event",
        user_id=str(event.payload.user_id),
        coins=event.payload.coins_to_award,
        new_balance=balance.amount,
        event_id=str(event.event_id),
    )


async def start_consumer() -> MessageConsumer:
    """Create, configure, and connect the RabbitMQ consumer.

    Returns:
        A connected MessageConsumer instance ready for ``.consume()``.
    """
    consumer = RabbitMQConsumer(
        url=rmq_settings.url,
        queue_name=rmq_settings.queue,
        exchange_name=rmq_settings.exchange,
        routing_key=rmq_settings.routing_key,
        dlq_name=f"{rmq_settings.queue}.dlq",
        prefetch_count=10,
    )
    await consumer.connect()
    return consumer
