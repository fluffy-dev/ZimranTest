from __future__ import annotations

import uuid
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import Depends, Header
from fastapi.exceptions import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.database.engine import db_helper


ISession = Annotated[AsyncSession, Depends(db_helper.get_session)]


def _get_redis() -> aioredis.Redis:
    from app.core.lifespan import redis_client

    return redis_client


IRedis = Annotated[aioredis.Redis, Depends(_get_redis)]


def _get_user_id(x_user_id: str = Header(..., alias="X-User-ID")) -> uuid.UUID:
    """Extracts and validates the caller's UUID from the X-User-ID request header."""
    try:
        return uuid.UUID(x_user_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid X-User-ID: must be a valid UUID.",
        )


IUserID = Annotated[uuid.UUID, Depends(_get_user_id)]


def _get_locale(accept_language: str = Header(default="en")) -> str:
    """Parses the primary locale from the Accept-Language header."""
    return (
        accept_language.split(",")[0].split(";")[0].split("-")[0].strip() or "en"
    )


ILocale = Annotated[str, Depends(_get_locale)]
