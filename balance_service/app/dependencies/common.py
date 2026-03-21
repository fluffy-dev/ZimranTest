from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Header
from fastapi.exceptions import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import db_helper


ISession = Annotated[AsyncSession, Depends(db_helper.get_session)]


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
