from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class BalanceResponseDTO(BaseModel):
    """API response schema for a user's current balance.

    Returned by ``GET /api/v1/balance``. Excludes the internal record ``id``
    to avoid leaking database internals to callers.

    Attributes:
        user_id: The UUID of the user whose balance is being reported.
        amount: Current virtual coin balance. Always ``>= 0``.
        updated_at: Timezone-aware datetime of the last balance modification.
    """

    user_id: uuid.UUID
    amount: int
    updated_at: datetime


class TransactionResponseDTO(BaseModel):
    """API response schema for a single ledger transaction.

    Each instance represents one immutable credit (or future debit) entry in
    the user's transaction history.

    Attributes:
        id: The UUID primary key of the transaction record.
        user_id: The UUID of the user who owns this transaction.
        type: Transaction kind — currently always ``"credit"``.
        amount: Number of coins transferred in this transaction.
        description: Optional human-readable note (e.g. quiz reward details).
            ``None`` if no description was provided at credit time.
        created_at: Timezone-aware timestamp of when the transaction was
            created. Immutable.
    """

    id: uuid.UUID
    user_id: uuid.UUID
    type: str
    amount: int
    description: str | None
    created_at: datetime


class TransactionListResponseDTO(BaseModel):
    """Paginated API response schema for a list of ledger transactions.

    Returned by ``GET /api/v1/balance/transactions``. Pagination metadata is
    echoed back from the request so clients can implement page navigation
    without parsing ``Link`` headers.

    Attributes:
        items: Ordered list of transactions for the requested page, sorted
            newest-first.
        page: The 1-based page number that was requested.
        page_size: The maximum number of items per page (1–100).
    """

    items: list[TransactionResponseDTO]
    page: int
    page_size: int
