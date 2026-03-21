from __future__ import annotations

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    """RFC 7807 Problem+JSON inspired error response."""
    error: ErrorDetail
