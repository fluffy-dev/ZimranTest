import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass
class BalanceEntity:
    """Domain representation of a user's virtual balance."""
    id: uuid.UUID
    user_id: uuid.UUID
    amount: int
    updated_at: datetime


@dataclass
class BalanceTransactionEntity:
    """Domain representation of an immutable transaction ledger."""
    id: uuid.UUID
    user_id: uuid.UUID
    type: str
    amount: int
    description: str | None
    idempotency_key: uuid.UUID
    created_at: datetime
