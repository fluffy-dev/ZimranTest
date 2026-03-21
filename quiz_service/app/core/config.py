from __future__ import annotations

from pydantic import PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Application
    APP_NAME: str = "quiz-service"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/quiz_db"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    QUIZ_CACHE_TTL: int = 60  # seconds

    # RabbitMQ
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    RABBITMQ_EXCHANGE: str = "finelo.events"
    RABBITMQ_ROUTING_KEY: str = "quiz.questions.rewarded"

    # Outbox poller
    OUTBOX_POLL_INTERVAL: float = 2.0  # seconds
    OUTBOX_BATCH_SIZE: int = 50

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 60


settings = Settings()
