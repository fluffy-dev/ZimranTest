from __future__ import annotations

import json

from src.config.project import settings
from src.config.database.session import AsyncSessionFactory
from src.balance.repositories.balance import BalanceRepository
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
    """
    Normalized MessageHandler for quiz.questions.rewarded events.
    Signature matches shared.messaging.base.MessageHandler.
    Raises on error → consumer will send to DLQ / seek-forward.
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

    async with AsyncSessionFactory() as session:
        async with session.begin():
            repo = BalanceRepository(session)
            service = BalanceService(repo)
            balance = await service.credit_from_quiz_event(event)
            logger.info(
                "Balance credited from quiz event",
                user_id=str(event.payload.user_id),
                coins=event.payload.coins_to_award,
                new_balance=balance.amount,
                event_id=str(event.event_id),
            )


async def start_consumer() -> MessageConsumer:
    consumer = RabbitMQConsumer(
        url=settings.RABBITMQ_URL,
        queue_name=settings.RABBITMQ_QUEUE,
        exchange_name=settings.RABBITMQ_EXCHANGE,
        routing_key=settings.RABBITMQ_ROUTING_KEY,
        dlq_name=f"{settings.RABBITMQ_QUEUE}.dlq",
        prefetch_count=10,
    )
    await consumer.connect()
    return consumer
