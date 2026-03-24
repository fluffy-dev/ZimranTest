from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from src.balance.enum import TransactionType


@dataclass(slots=True)
class BalanceEntity:
    """Domain representation of a user's virtual coin balance.

    This is a pure Python dataclass used in the service and repository layers
    as a framework-agnostic alternative to the SQLAlchemy ORM model. It holds
    a single, mutable balance record that is upserted on every credit operation.

    Attributes:
        id: Internal primary key (UUID) of the balance record.
        user_id: Unique identifier of the user who owns this balance.
            Each user has at most one balance record (enforced by a unique
            constraint on the ``balances`` table).
        amount: Current virtual coin balance. Always non-negative; enforced at
            the database level with a ``CHECK (amount >= 0)`` constraint.
        updated_at: Timezone-aware timestamp of the last balance modification,
            automatically set by the database on every upsert.
    """

    id: uuid.UUID
    user_id: uuid.UUID
    amount: int
    updated_at: datetime


@dataclass(slots=True)
class BalanceTransactionEntity:
    """Domain representation of an immutable ledger entry for a balance change.

    Every credit operation appends a new ``BalanceTransactionEntity`` to the
    ledger. Records are never deleted or updated — they serve as an audit trail
    and as the idempotency guard for event-driven credits.

    Attributes:
        id: Internal primary key (UUID) of the transaction record.
        user_id: Identifier of the user whose balance was affected.
        type: The kind of transaction. Currently always ``"credit"``; reserved
            for future ``"debit"`` operations.
        amount: The number of coins involved in this transaction. May be zero
            for initialisation events but is never negative.
        description: Optional human-readable note attached to the transaction
            (e.g. ``"Quiz reward: attempt <uuid>"``). ``None`` if omitted.
        idempotency_key: Unique key (sourced from the upstream event ID) that
            prevents double-application of the same event. Protected by a
            unique constraint on the ``balance_transactions`` table.
        created_at: Timezone-aware timestamp set by the database on insert.
            Immutable once written.
    """

    id: uuid.UUID
    user_id: uuid.UUID
    type: TransactionType
    amount: int
    description: str | None
    idempotency_key: uuid.UUID
    created_at: datetime
