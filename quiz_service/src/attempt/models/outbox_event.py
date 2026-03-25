import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Column,
    DateTime,
    Index,
    Integer,
    String,
    func
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.libs.base_model import Base


class OutboxEvent(Base):
    """
    SQLAlchemy model for the Transactional Outbox pattern.
    Stores events that need to be published to external systems (e.g., RabbitMQ).
    """

    __tablename__ = "outbox_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    routing_key: Mapped[str] = mapped_column(String(200), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (
        Index(
            "idx_outbox_pending",
            "published_at",
            postgresql_where=Column("published_at").is_(None),
        ),
    )
