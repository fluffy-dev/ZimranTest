from __future__ import annotations

import asyncio
import aio_pika
import aio_pika.abc

from shared.logging import get_logger
from shared.messaging.base import MessageHandler

logger = get_logger(__name__)


class RabbitMQPublisher:

    def __init__(
        self,
        url: str,
        exchange_name: str = "finelo.events",
        exchange_type: aio_pika.ExchangeType = aio_pika.ExchangeType.TOPIC,
    ) -> None:
        self._url = url
        self._exchange_name = exchange_name
        self._exchange_type = exchange_type
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._channel: aio_pika.abc.AbstractRobustChannel | None = None
        self._exchange: aio_pika.abc.AbstractExchange | None = None

    @property
    def is_connected(self) -> bool:
        """Returns True when the publisher has an active open connection."""
        return (
            self._connection is not None
            and not self._connection.is_closed
            and self._exchange is not None
        )

    async def connect(self) -> None:
        self._connection = await aio_pika.connect_robust(self._url)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=1)
        self._exchange = await self._channel.declare_exchange(
            self._exchange_name, self._exchange_type, durable=True
        )
        logger.info("RabbitMQ publisher connected", exchange=self._exchange_name)

    async def publish(self, routing_key: str, body: bytes, message_id: str) -> None:
        if self._exchange is None:
            raise RuntimeError("Publisher not connected. Call connect() first.")
        message = aio_pika.Message(
            body=body,
            content_type="application/json",
            message_id=message_id,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await self._exchange.publish(message, routing_key=routing_key)
        logger.debug("Event published", routing_key=routing_key, message_id=message_id)

    async def close(self) -> None:
        if self._connection:
            await self._connection.close()
            logger.info("RabbitMQ publisher connection closed")


class RabbitMQConsumer:

    def __init__(
        self,
        url: str,
        queue_name: str,
        exchange_name: str = "finelo.events",
        routing_key: str = "#",
        dlq_name: str | None = None,
        prefetch_count: int = 10,
    ) -> None:
        self._url = url
        self._queue_name = queue_name
        self._exchange_name = exchange_name
        self._routing_key = routing_key
        self._dlq_name = dlq_name or f"{queue_name}.dlq"
        self._prefetch_count = prefetch_count
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._channel: aio_pika.abc.AbstractRobustChannel | None = None
        self._queue: aio_pika.abc.AbstractQueue | None = None

    @property
    def is_connected(self) -> bool:
        """Returns True when the consumer has an active open connection and queue."""
        return (
            self._connection is not None
            and not self._connection.is_closed
            and self._queue is not None
        )

    async def connect(self) -> None:
        self._connection = await aio_pika.connect_robust(self._url)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=self._prefetch_count)

        dlq = await self._channel.declare_queue(self._dlq_name, durable=True)
        exchange = await self._channel.declare_exchange(
            self._exchange_name, aio_pika.ExchangeType.TOPIC, durable=True
        )
        dlx_name = f"{self._dlq_name}.exchange"
        dlx = await self._channel.declare_exchange(
            dlx_name, aio_pika.ExchangeType.DIRECT, durable=True
        )
        await dlq.bind(dlx, routing_key=self._dlq_name)

        self._queue = await self._channel.declare_queue(
            self._queue_name,
            durable=True,
            arguments={
                "x-dead-letter-exchange": dlx_name,
                "x-dead-letter-routing-key": self._dlq_name,
                "x-message-ttl": 60000,
            },
        )
        await self._queue.bind(exchange, routing_key=self._routing_key)
        logger.info(
            "RabbitMQ consumer connected",
            queue=self._queue_name,
            routing_key=self._routing_key,
        )

    async def consume(self, handler: MessageHandler) -> None:
        """
        Consume messages using the normalized MessageHandler signature.
        Bridges aio_pika's IncomingMessage → (body, routing_key, message_id).
        """
        if self._queue is None:
            raise RuntimeError("Consumer not connected. Call connect() first.")
        async with self._queue.iterator() as queue_iter:
            async for message in queue_iter:
                try:
                    await handler(
                        message.body,
                        message.routing_key or "",
                        message.message_id or "",
                    )
                    await message.ack()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.error(
                        "Message processing failed — sending to DLQ",
                        error=str(exc),
                        message_id=message.message_id,
                    )
                    await message.nack(requeue=False)

    async def close(self) -> None:
        if self._connection:
            await self._connection.close()
            logger.info("RabbitMQ consumer connection closed")