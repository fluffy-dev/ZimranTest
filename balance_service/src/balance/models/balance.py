from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.libs.base_model import Base


class Balance(Base):
    """SQLAlchemy ORM model for the ``balances`` table.

    Represents a user's current virtual coin balance. There is exactly one row
    per user, enforced by a unique constraint on ``user_id``. The record is
    created on first credit and updated in-place on every subsequent credit via
    an ``INSERT … ON CONFLICT DO UPDATE`` (upsert) statement.

    Table: ``balances``

    Columns:
        id (UUID): Primary key, generated automatically with :func:`uuid.uuid4`.
        user_id (UUID): Foreign-key-like reference to the owning user. Unique —
            every user has at most one balance row.
        amount (BigInteger): Current coin balance. Always ``>= 0`` — enforced
            by the database-level check constraint
            ``ck_balance_non_negative``.
        updated_at (DateTime with TZ): Set to ``NOW()`` on insert by the
            database; automatically refreshed on every UPDATE via
            ``onupdate=func.now()``.

    Constraints / Indexes:
        - ``CHECK (amount >= 0)`` — ``ck_balance_non_negative``
        - ``UNIQUE (user_id)`` (inline ``unique=True``)
        - ``INDEX idx_balances_user_id`` on ``user_id`` for fast lookups
    """

    __tablename__ = "balances"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_balance_non_negative"),
        Index("idx_balances_user_id", "user_id"),
    )


class BalanceTransaction(Base):
    """SQLAlchemy ORM model for the ``balance_transactions`` table.

    Represents a single, immutable ledger entry for a balance change. Rows are
    only ever inserted — never updated or deleted. This provides a full audit
    trail and acts as the idempotency guard: the unique constraint on
    ``idempotency_key`` prevents the same upstream event from being applied
    more than once.

    The ``idempotency_key`` is sourced directly from the ``event_id`` of the
    ``QuizRewardEvent`` published by the quiz service outbox.

    Table: ``balance_transactions``

    Columns:
        id (UUID): Primary key, generated automatically with :func:`uuid.uuid4`.
        user_id (UUID): Identifier of the user whose balance was affected.
            Not a hard foreign key to keep the schema loosely coupled.
        type (String[10]): Transaction kind — currently always ``"credit"``;
            reserved for future ``"debit"`` support.
        amount (BigInteger): Number of coins transferred. Can be ``0`` for
            initialisation synthetic transactions but is never negative.
        description (String[255], nullable): Optional human-readable annotation
            (e.g. ``"Quiz reward: attempt <uuid>"``).
        idempotency_key (UUID): Unique key that prevents double-credit.
            Sourced from the upstream event ID. Protected by a unique
            constraint and a dedicated index.
        created_at (DateTime with TZ): Immutable creation timestamp, set by
            the database on insert.

    Constraints / Indexes:
        - ``UNIQUE (idempotency_key)`` (inline ``unique=True``)
        - ``INDEX idx_txn_user_id`` on ``user_id`` for per-user queries
        - ``INDEX idx_txn_idempotency_key`` on ``idempotency_key`` for fast
          duplicate detection
    """

    __tablename__ = "balance_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    type: Mapped[str] = mapped_column(String(10), nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    idempotency_key: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_txn_amount_positive"),
        CheckConstraint(
            "type IN ('credit', 'debit')", name="ck_txn_type_valid"
        ),
        Index("idx_txn_user_id", "user_id"),
        Index("idx_txn_idempotency_key", "idempotency_key"),
    )
