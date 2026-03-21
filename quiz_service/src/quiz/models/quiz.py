import uuid
from enum import Enum
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.libs.base_model import Base, TimestampMixin


class QuestionType(str, Enum):
    SINGLE_CHOICE = "single_choice"
    FILL_GAP = "fill_gap"
    MULTIPLE_CHOICE = "multiple_choice"
    MATCHING = "matching"


class Quiz(TimestampMixin, Base):
    """
    A quiz with localized title and description.
    title/description stored as JSONB: {"en": "...", "de": "...", "tr": "...", ...}
    """

    __tablename__ = "quizzes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    description: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    questions: Mapped[list["Question"]] = relationship(
        "Question", back_populates="quiz", cascade="all, delete-orphan", lazy="selectin"
    )
    attempts: Mapped[list["QuizAttempt"]] = relationship(
        "QuizAttempt", back_populates="quiz"
    )


class Question(TimestampMixin, Base):
    """
    A quiz question. Type-specific data is stored in JSONB payload.

    Payload shapes:
    - single_choice:   {"options": [{"id": str, "text": {locale: str}}, ...], "correct_id": str}
    - fill_gap:        {"correct_answers": [str, ...]}  (list of accepted strings, case-insensitive)
    - multiple_choice: {"options": [{"id": str, "text": {locale: str}}, ...], "correct_ids": [str, ...]}
    - matching:        {"pairs": [{"id": str, "left": {locale: str}, "right": {locale: str}}, ...]}
    """

    __tablename__ = "questions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    quiz_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    text: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    quiz: Mapped[Quiz] = relationship("Quiz", back_populates="questions")
    answers: Mapped[list["UserQuestionAnswer"]] = relationship(
        "UserQuestionAnswer", back_populates="question"
    )

    __table_args__ = (
        Index("idx_questions_quiz_id", "quiz_id"),
        Index("idx_questions_quiz_order", "quiz_id", "order_index"),
    )
