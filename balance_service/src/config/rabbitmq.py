from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """RabbitMQ connection and routing configuration."""
    url: str = Field("amqp://guest:guest@localhost:5672/", alias="RABBITMQ_URL")
    exchange: str = Field("finelo.events", alias="RABBITMQ_EXCHANGE")
    queue: str = Field("balance.quiz_reward", alias="RABBITMQ_QUEUE")
    routing_key: str = Field("quiz.questions.rewarded", alias="RABBITMQ_ROUTING_KEY")

settings = Settings()
