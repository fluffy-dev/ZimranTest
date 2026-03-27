from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Attempt abandonment background job configuration."""
    abandon_poll_interval: float = Field(60.0, alias="ATTEMPT_ABANDON_POLL_INTERVAL")
    abandon_timeout_minutes: int = Field(60, alias="ATTEMPT_ABANDON_TIMEOUT_MINUTES")


settings = Settings()
