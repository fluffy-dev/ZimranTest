from __future__ import annotations

from pydantic import EmailStr, AnyUrl, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """OpenAPI / Swagger documentation configuration."""

    title: str = Field(default="Finelo Balance Service", alias="APP_TITLE")
    description: str | None = Field(default=None, alias="APP_DESCRIPTION")
    summary: str | None = Field(None, alias="APP_SUMMARY")
    terms_of_service: str | None = Field(None, alias="APP_TERMS_OF_SERVICE")
    licence_name: str = Field("MIT", alias="APP_LICENSE_NAME")
    licence_identifier: str = Field("MIT", alias="APP_LICENSE_IDENTIFIER")
    licence_url: AnyUrl | None = Field(
        "https://rem.mit-license.org/license.txt", alias="APP_LICENSE_URL"
    )
    contact_name: str | None = Field("Finelo Team", alias="APP_CONTACT_NAME")
    contact_url: AnyUrl | None = Field(
        "https://finelo.com", alias="APP_CONTACT_URL"
    )
    contact_email: EmailStr | None = Field(
        "team@finelo.com", alias="APP_CONTACT_EMAIL"
    )
    docs_url: str | None = Field("/docs", alias="APP_DOCS_URL")
    redoc_url: str | None = Field("/redoc", alias="APP_REDOC_URL")

    @property
    def contact(self) -> dict:
        """Builds the OpenAPI contact info dictionary."""
        return {
            "name": self.contact_name,
            "url": self.contact_url,
            "email": self.contact_email,
        }

    @property
    def license(self) -> dict:
        """Builds the OpenAPI license info dictionary."""
        return {
            "name": self.licence_name,
            "url": self.licence_url,
            "identifier": self.licence_identifier,
        }


settings = Settings()
