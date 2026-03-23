import uuid
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header
from fastapi.exceptions import HTTPException

class HEADERS:
    """Standard HTTP header names used across the platform."""

    USER_ID = "X-User-ID"
    CORRELATION_ID = "X-Correlation-ID"


def _get_user_id(x_user_id: str = Header(..., alias=HEADERS.USER_ID)) -> uuid.UUID:
    """Extract and validate the caller's UUID from the ``X-User-ID`` request header.

    The header is mandatory. Requests that omit it will receive a ``422``
    response from FastAPI's built-in request validation before this function
    is ever called.

    Args:
        x_user_id: Raw header string automatically injected by FastAPI.
            Expected to be a valid UUID in canonical form
            (e.g. ``"550e8400-e29b-41d4-a716-446655440000"``).

    Returns:
        A :class:`uuid.UUID` object parsed from the header value.

    Raises:
        HTTPException: With status ``400`` if ``x_user_id`` is not a valid UUID
            string.
    """
    try:
        return uuid.UUID(x_user_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid X-User-ID: must be a valid UUID.",
        )

IUserID: type[UUID] = Annotated[uuid.UUID, Depends(_get_user_id)]
"""FastAPI-injected caller UUID resolved from the ``X-User-ID`` header.

Usage::

    async def my_endpoint(user_id: IUserID) -> ...:
        ...
"""
