"""
Kafka implementation of the MessagePublisher and MessageConsumer protocols.

Requires: pip install aiokafka

To switch from RabbitMQ to Kafka, change ONE line in each service:

  # quiz_service/app/core/lifespan.py
  - from shared.messaging.rabbitmq import RabbitMQPublisher
  + from shared.messaging.kafka import KafkaPublisher

  # balance_service/app/messaging/consumer.py
  - from shared.messaging.rabbitmq import RabbitMQConsumer
  + from shared.messaging.kafka import KafkaConsumer

Everything else stays the same — handler signature, connect/close lifecycle.
"""
from __future__ import annotations

from shared.logging import get_logger
from shared.messaging.base import MessageHandler

logger = get_logger(__name__)


class KafkaPublisher:
    """
    Kafka implementation of MessagePublisher.

    Uses `routing_key` as the Kafka topic name.
    `message_id` is set as the Kafka message key for consumer-side deduplication.
    """

    def __init__(self, bootstrap_servers: str, topic: str) -> None:
        self._bootstrap_servers = bootstrap_servers
        self._topic = topic
        self._producer = None

    async def connect(self) -> None:
        from aiokafka import AIOKafkaProducer  # noqa: PLC0415

        self._producer = AIOKafkaProducer(bootstrap_servers=self._bootstrap_servers)
        await self._producer.start()
        logger.info("Kafka producer connected", servers=self._bootstrap_servers)

    async def publish(self, routing_key: str, body: bytes, message_id: str) -> None:
        if self._producer is None:
            raise RuntimeError("KafkaPublisher not connected. Call connect() first.")
        # `routing_key` maps to topic; `message_id` is the Kafka record key
        await self._producer.send_and_wait(
            topic=routing_key,
            value=body,
            key=message_id.encode(),
        )
        logger.debug("Kafka event published", topic=routing_key, key=message_id)

    async def close(self) -> None:
        if self._producer:
            await self._producer.stop()
            logger.info("Kafka producer disconnected")


class KafkaConsumer:
    """
    Kafka implementation of MessageConsumer.

    Commits offsets only AFTER successful handler invocation (at-least-once).
    Failed messages are logged; offset is NOT committed → retried on restart.
    """

    def __init__(
        self,
        bootstrap_servers: str,
        topic: str,
        group_id: str,
    ) -> None:
        self._bootstrap_servers = bootstrap_servers
        self._topic = topic
        self._group_id = group_id
        self._consumer = None

    async def connect(self) -> None:
        from aiokafka import AIOKafkaConsumer  # noqa: PLC0415

        self._consumer = AIOKafkaConsumer(
            self._topic,
            bootstrap_servers=self._bootstrap_servers,
            group_id=self._group_id,
            enable_auto_commit=False,  # manual commit after success
            auto_offset_reset="earliest",
        )
        await self._consumer.start()
        logger.info(
            "Kafka consumer connected",
            topic=self._topic,
            group_id=self._group_id,
        )

    async def consume(self, handler: MessageHandler) -> None:
        if self._consumer is None:
            raise RuntimeError("KafkaConsumer not connected. Call connect() first.")

        async for message in self._consumer:
            try:
                await handler(
                    message.value,
                    message.topic,
                    (message.key or b"").decode(),
                )
                # Commit only after successful processing
                await self._consumer.commit()
            except Exception as exc:
                logger.error(
                    "Kafka message processing failed — offset NOT committed",
                    topic=message.topic,
                    offset=message.offset,
                    error=str(exc),
                )
                # No commit → retried from this offset on next restart

    async def close(self) -> None:
        if self._consumer:
            await self._consumer.stop()
            logger.info("Kafka consumer disconnected")
