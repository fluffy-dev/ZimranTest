"""
Public re-exports for the messaging package.

Architectural contract:
  - Services import from here using ONLY the abstract Protocol types.
  - Services construct concrete adapters (RabbitMQPublisher, KafkaPublisher)
    in their lifespan/config — one line to change the broker.

Example (quiz_service lifespan.py):
    from shared.messaging import MessagePublisher
    from shared.messaging.rabbitmq import RabbitMQPublisher   # ← swap this line

    publisher: MessagePublisher = RabbitMQPublisher(url=..., exchange_name=...)
"""
from shared.messaging.base import MessageConsumer, MessageHandler, MessagePublisher
from shared.messaging.kafka import KafkaConsumer, KafkaPublisher
from shared.messaging.rabbitmq import RabbitMQConsumer, RabbitMQPublisher

# Backwards-compatible aliases (old code that imported AsyncRabbitMQPublisher still works)
AsyncRabbitMQPublisher = RabbitMQPublisher
AsyncRabbitMQConsumer = RabbitMQConsumer

__all__ = [
    # Abstract interface — always import these in type annotations
    "MessagePublisher",
    "MessageConsumer",
    "MessageHandler",
    # Concrete adapters
    "RabbitMQPublisher",
    "RabbitMQConsumer",
    "KafkaPublisher",
    "KafkaConsumer",
    # Backwards-compat
    "AsyncRabbitMQPublisher",
    "AsyncRabbitMQConsumer",
]
