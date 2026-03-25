import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.libs.base_model import Base
from src.quiz.models.question import Question
from src.attempt.models.quiz_attempt import QuizAttempt


class UserQuestionAnswer(Base):
    """
    SQLAlchemy model storing a user's answer.
    Allows is_correct to be null to support saving draft answers before submission.
    """

    __tablename__ = "user_question_answers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("quiz_attempts.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )

    answer_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    answered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    attempt: Mapped[QuizAttempt] = relationship("QuizAttempt", back_populates="answers")
    question: Mapped[Question] = relationship("Question", back_populates="answers")

    __table_args__ = (
        Index("idx_uqa_attempt_id", "attempt_id"),
        Index("idx_uqa_question_id", "question_id"),
        Index("idx_uqa_attempt_question_unique", "attempt_id", "question_id", unique=True),
    )