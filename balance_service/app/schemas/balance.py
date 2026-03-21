from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class BalanceResponse(BaseModel):
    user_id: uuid.UUID
    amount: int
    updated_at: datetime


class TransactionResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    type: str
    amount: int
    description: str | None
    created_at: datetime


class TransactionListResponse(BaseModel):
    items: list[TransactionResponse]
    page: int
    page_size: int
