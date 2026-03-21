from __future__ import annotations

from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    APP_TITLE: str = "Quiz Service"
    APP_DESCRIPTION: str = "Microservice for managing and grading quizzes."
    APP_SUMMARY: str = "Finelo Quiz Microservice"
    APP_VERSION: str = "1.0.0"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    APP_DEBUG: bool = False
    APP_HOOKS_ENABLED: bool = True
    APP_ROOT_PATH: str = ""
    APP_TIMEZONE_SHIFT: int = 3
    
    # Docs
    APP_DOCS_URL: str = "/docs"
    APP_REDOC_URL: str = "/redoc"
    APP_TERMS_OF_SERVICE: str = ""
    APP_LICENSE_NAME: str = "MIT"
    APP_LICENSE_IDENTIFIER: str = "MIT"
    APP_LICENSE_URL: str = "https://rem.mit-license.org/license.txt"
    APP_CONTACT_NAME: str = "Zimran"
    APP_CONTACT_URL: str = ""
    APP_CONTACT_EMAIL: str = ""

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/quiz_db"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_ECHO_LOG: bool = False
    DB_RUN_AUTO_MIGRATE: bool = True

    # Logging
    LOGGING_ON: bool = True
    LOG_LEVEL: str = "INFO"
    LOGGING_JSON: bool = False

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    QUIZ_CACHE_TTL: int = 60  # seconds

    # RabbitMQ
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    RABBITMQ_EXCHANGE: str = "finelo.events"
    RABBITMQ_ROUTING_KEY: str = "quiz.questions.rewarded"

    # Background workers
    OUTBOX_POLL_INTERVAL: float = 2.0  # seconds
    OUTBOX_BATCH_SIZE: int = 50

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 60

    # CORS
    CORS_ALLOW_ORIGINS: list[str] | str = ["*"]
    CORS_ALLOW_METHODS: list[str] | str = ["*"]
    CORS_ALLOW_HEADERS: list[str] | str = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_EXPOSE_HEADERS: list[str] | str = ["*"]
    CORS_MAX_AGE: int = 600

    @property
    def fastapi_kwargs(self) -> dict[str, Any]:
        """Provides dynamic configuration parameters for FastAPI application initialization."""
        return {
            "title": self.APP_TITLE,
            "description": self.APP_DESCRIPTION,
            "version": self.APP_VERSION,
            "debug": self.APP_DEBUG,
            "summary": self.APP_SUMMARY,
            "docs_url": self.APP_DOCS_URL,
            "redoc_url": self.APP_REDOC_URL,
            "root_path": self.APP_ROOT_PATH,
            "terms_of_service": self.APP_TERMS_OF_SERVICE or None,
            "contact": {
                "name": self.APP_CONTACT_NAME,
                "url": self.APP_CONTACT_URL or None,
                "email": self.APP_CONTACT_EMAIL or None,
            } if self.APP_CONTACT_NAME else None,
            "license_info": {
                "name": self.APP_LICENSE_NAME,
                "identifier": self.APP_LICENSE_IDENTIFIER or None,
                "url": self.APP_LICENSE_URL or None,
            } if self.APP_LICENSE_NAME else None,
        }


settings = Settings()
