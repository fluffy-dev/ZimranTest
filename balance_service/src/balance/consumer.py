from __future__ import annotations

from src.config.rabbitmq import settings as rmq_settings
from src.config.database.engine import db_helper
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
    """Processes a single quiz reward RabbitMQ message.

    Deserializes the raw message body, validates it against the expected
    schema, and orchestrates the balance credit via the domain service.
    Any unhandled exception will propagate up, signaling the AMQP broker
    to negative-acknowledge (NACK) the message and route it to the
    Dead Letter Queue (DLQ).

    Args:
        body: Raw UTF-8 encoded JSON message body received from RabbitMQ.
        routing_key: The AMQP routing key used to deliver the message.
        message_id: The AMQP message identifier for correlation.

    Raises:
        Exception: If schema validation fails, database connectivity drops,
            or transactional commits fail. Propagating the error ensures
            proper DLQ routing.
    """
    logger.info(
        "Received quiz reward message",
        routing_key=routing_key,
        message_id=message_id,
    )

    try:
        event = QuizRewardEvent.model_validate_json(body)
    except Exception as exc:
        logger.error(
            "Failed to deserialize quiz reward event",
            error=str(exc),
            raw=body.decode("utf-8")[:300]
        )
        raise

    uow = SqlAlchemyUnitOfWork(session_factory=db_helper.session_factory)

    async with uow:
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
    """Creates, configures, and connects the RabbitMQ consumer.

    Reads connection parameters from the environment settings and binds
    to the designated exchange and routing key. Configures a Dead Letter
    Queue for unprocessable messages and sets a prefetch count to balance
    memory pressure with throughput.

    Returns:
        A connected MessageConsumer instance ready for consumption.
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