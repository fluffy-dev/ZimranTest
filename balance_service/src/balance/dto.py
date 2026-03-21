from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class BalanceResponseDTO(BaseModel):
    user_id: uuid.UUID
    amount: int
    updated_at: datetime


class TransactionResponseDTO(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    type: str
    amount: int
    description: str | None
    created_at: datetime


class TransactionListResponseDTO(BaseModel):
    items: list[TransactionResponseDTO]
    page: int
    page_size: int
