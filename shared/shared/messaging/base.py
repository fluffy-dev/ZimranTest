"""
Abstract message broker interface (Protocol-based).

The 0.1% principle:
  Services depend on these abstract types ONLY.
  Swap the broker (RabbitMQ → Kafka → SQS) by changing ONE line in lifespan/consumer.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol, runtime_checkable


# Type alias for message handler callbacks
MessageHandler = Callable[[bytes, str, str], Awaitable[None]]
"""
Args:
    body       (bytes) – raw message body
    routing_key (str)  – topic / routing key / Kafka topic key
    message_id  (str)  – unique message identifier (for dedup/logging)
"""


@runtime_checkable
class MessagePublisher(Protocol):
    """Abstract publisher. Publish bytes to a routing key."""

    async def connect(self) -> None:
        """Open connection and any required channels/producers."""
        ...

    async def publish(
        self,
        routing_key: str,
        body: bytes,
        message_id: str,
    ) -> None:
        """Publish a single message. Must be idempotent-safe."""
        ...

    async def close(self) -> None:
        """Gracefully close the connection."""
        ...


@runtime_checkable
class MessageConsumer(Protocol):
    """Abstract consumer. Consume messages and call handler."""

    async def connect(self) -> None:
        """Open connection and subscribe to queues/topics."""
        ...

    async def consume(self, handler: MessageHandler) -> None:
        """
        Start consuming. Blocks until cancelled.
        Contract:
          - On success: ack the message
          - On handler exception: nack / send to DLQ / seek-forward
        """
        ...

    async def close(self) -> None:
        """Gracefully close the connection."""
        ...
