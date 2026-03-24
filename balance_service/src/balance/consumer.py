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

    This is the normalised :data:`~shared.messaging.base.MessageHandler`
    callback. It deserialises the raw message body, validates it against
    :class:`~shared.schemas.QuizRewardEvent`, then opens a fresh database
    session and commits a credit to the affected user's balance via
    :class:`BalanceService`.

    The entire operation runs inside ``session.begin()`` so that any unhandled
    exception triggers a rollback. Re-raising the exception on failure signals
    the consumer to route the message to the dead-letter queue (DLQ) rather
    than acknowledging it.

    Args:
        body: Raw UTF-8–encoded JSON message body received from RabbitMQ.
        routing_key: The routing key the message was published with (used for
            logging and future routing decisions).
        message_id: The AMQP ``message-id`` property, used for correlation in
            log output.

    Raises:
        Exception: Any error encountered during JSON parsing, schema
            validation, or the database write is re-raised so that the
            consumer can nack the message and route it to the DLQ.
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
        raise  # nack to DLQ

    async with SqlAlchemyUnitOfWork() as uow:
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

    Reads all connection parameters from
    :data:`~src.config.rabbitmq.settings` and creates a
    :class:`~shared.messaging.rabbitmq.RabbitMQConsumer` that will:

    - Bind to the configured exchange and routing key.
    - Route unprocessable messages to a dead-letter queue named
      ``<queue_name>.dlq``.
    - Pre-fetch up to 10 messages concurrently to balance throughput and
      memory pressure.

    This function only establishes the AMQP connection; it does **not** start
    consuming messages. Call ``consumer.consume(handle_quiz_reward_message)``
    (typically via :func:`asyncio.create_task`) to begin processing.

    Returns:
        A connected :class:`~shared.messaging.base.MessageConsumer` instance
        ready to have ``.consume()`` called on it.
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
