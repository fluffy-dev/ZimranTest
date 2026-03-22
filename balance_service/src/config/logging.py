from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Logging configuration loaded from environment variables."""

    logging_on: bool = Field(default=True, alias="LOGGING_ON")
    logging_level: str = Field(default="DEBUG", alias="LOGGING_LEVEL")
    logging_json: bool = Field(default=True, alias="LOGGING_JSON")


settings = Settings()
