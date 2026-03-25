import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum as SQLEnum, ForeignKey, Index, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.attempt.enum import AttemptStatusEnum
from src.libs.base_model import Base
from src.quiz.models.quiz import Quiz


class QuizAttempt(Base):
    """
    SQLAlchemy model tracking a user's attempt at a quiz.
    Supports time-to-live (TTL) tracking via updated_at for abandoned sessions.
    """

    __tablename__ = "quiz_attempts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    quiz_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    status: Mapped[AttemptStatusEnum] = mapped_column(
        SQLEnum(AttemptStatusEnum, native_enum=False, length=20),
        default=AttemptStatusEnum.IN_PROGRESS,
        nullable=False,
    )

    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_questions: Mapped[int | None] = mapped_column(Integer, nullable=True)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    quiz: Mapped[Quiz] = relationship("Quiz", back_populates="attempts")
    answers: Mapped[list["UserQuestionAnswer"]] = relationship(
        "UserQuestionAnswer", back_populates="attempt", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_quiz_attempts_quiz_id", "quiz_id"),
        Index("idx_quiz_attempts_user_quiz", "user_id", "quiz_id"),
        CheckConstraint("score >= 0", name="chk_quiz_attempts_score_positive"),
        CheckConstraint("total_questions > 0", name="chk_quiz_attempts_total_positive"),
    )