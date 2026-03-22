from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Outbox poller configuration for interval and batch size."""
    poll_interval: float = Field(2.0, alias="OUTBOX_POLL_INTERVAL")
    batch_size: int = Field(50, alias="OUTBOX_BATCH_SIZE")

settings = Settings()
