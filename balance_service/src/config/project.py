from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    APP_NAME: str = "balance-service"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/balance_db"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    RABBITMQ_EXCHANGE: str = "finelo.events"
    RABBITMQ_QUEUE: str = "balance.quiz_reward"
    RABBITMQ_ROUTING_KEY: str = "quiz.questions.rewarded"


settings = Settings()
