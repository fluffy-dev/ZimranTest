from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Redis connection and cache TTL configuration."""
    url: str = Field("redis://localhost:6379/0", alias="REDIS_URL")
    quiz_cache_ttl: int = Field(60, alias="QUIZ_CACHE_TTL")

settings = Settings()
