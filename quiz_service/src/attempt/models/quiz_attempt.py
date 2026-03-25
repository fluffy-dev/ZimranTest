import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
    Enum as SQLEnum,
    CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.attempt.enum import AttemptStatusEnum
from src.libs.base_model import Base
from src.quiz.models.quiz import Quiz


class QuizAttempt(Base):
    """
    SQLAlchemy model tracking a single user's attempt at a quiz.
    Stores metadata like status, score, and timestamps.
    """

    __tablename__ = "quiz_attempts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    quiz_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quizzes.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[AttemptStatusEnum] = mapped_column(
        SQLEnum(AttemptStatusEnum, native_enum=False, length=20),
        String(20), default=AttemptStatusEnum.IN_PROGRESS, nullable=False
    )
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_questions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
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
        CheckConstraint('score >= 0', name='check_score_positive'),
        CheckConstraint('total_questions > 0', name='check_total_questions_positive'),
    )
