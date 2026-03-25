import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.libs.base_model import Base


class UserRewardedQuestion(Base):
    """
    SQLAlchemy model recording questions for which a user has already received rewards.
    Uses a composite primary key (user_id, question_id) for idempotency.
    """

    __tablename__ = "user_rewarded_questions"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("questions.id"),
        primary_key=True,
    )
    rewarded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
