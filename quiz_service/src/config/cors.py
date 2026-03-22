from __future__ import annotations

import json
from typing import Any

from pydantic import Field
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
)


class MyCustomSource(EnvSettingsSource):
    """Parses comma-separated environment values into Python lists."""

    def prepare_field_value(
        self, field_name: str, field: FieldInfo, value: Any, value_is_complex: bool
    ) -> Any:
        if field_name in [
            "allow_origins",
            "allow_methods",
            "allow_headers",
            "expose_headers",
        ]:
            if value:
                return value.split(",")
        return json.loads(value) if value else value


class Settings(BaseSettings):
    """CORS middleware configuration loaded from environment variables."""

    allow_origins: list[str] = Field(default=["*"], alias="CORS_ALLOW_ORIGINS")
    allow_methods: list[str] = Field(default=["GET"], alias="CORS_ALLOW_METHODS")
    allow_headers: list[str] = Field(default=["*"], alias="CORS_ALLOW_HEADERS")
    allow_credentials: bool = Field(default=False, alias="CORS_ALLOW_CREDENTIALS")
    allow_origin_regex: str | None = Field(None, alias="CORS_ALLOW_ORIGIN_REGEX")
    expose_headers: list[str] = Field(default=["*"], alias="CORS_EXPOSE_HEADERS")
    max_age: int = Field(default=600, alias="CORS_MAX_AGE")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (MyCustomSource(settings_cls),)


settings = Settings()

