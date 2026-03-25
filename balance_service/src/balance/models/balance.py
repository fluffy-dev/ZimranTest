from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, func
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
    )
