from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Enum as SQLEnum, ForeignKey, Index, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.libs.base_model import Base, TimestampMixin
from src.quiz.enum import QuestionType

if TYPE_CHECKING:
    from src.quiz.models.quiz import Quiz
    from src.attempt.models.user_question_answer import UserQuestionAnswer


class Question(TimestampMixin, Base):
    """SQLAlchemy model representing a single evaluation unit within a quiz.

    Attributes:
        id: The unique UUID primary key.
        quiz_id: The foreign key referencing the parent quiz entity.
        type: The structural type of the question, strictly constrained by QuestionType.
        order_index: The integer representing the sequential display order.
        text: A dictionary containing localized question instructions.
        payload: A dictionary containing type-specific configuration and validation data.
        quiz: The parent quiz entity relation.
        answers: A collection of user submitted answers linked to this question.
    """

    __tablename__ = "questions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    quiz_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False
    )

    type: Mapped[QuestionType] = mapped_column(
        SQLEnum(QuestionType, native_enum=False, length=30),
        nullable=False
    )

    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    text: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    quiz: Mapped[Quiz] = relationship(
        "Quiz",
        back_populates="questions",
    )
    answers: Mapped[list[UserQuestionAnswer]] = relationship(
        "UserQuestionAnswer",
        back_populates="question",
    )

    __table_args__ = (
        Index("idx_questions_quiz_id", "quiz_id"),
        Index("idx_questions_quiz_order", "quiz_id", "order_index"),
    )