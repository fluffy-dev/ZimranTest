from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.libs.base_model import Base, TimestampMixin

if TYPE_CHECKING:
    from src.attempt.models.quiz_attempt import QuizAttempt
    from src.quiz.models.question import Question

class Quiz(TimestampMixin, Base):
    """SQLAlchemy model representing a strictly localized quiz entity.

    Attributes:
        id: The unique UUID primary key.
        title: A dictionary containing localized titles keyed by language code.
        description: A dictionary containing localized descriptions, or None if absent.
        is_active: A boolean flag indicating if the quiz is accessible for attempts.
        questions: A collection of associated question entities.
        attempts: A collection of user attempt entities associated with this quiz.
    """

    __tablename__ = "quizzes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    description: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    questions: Mapped[list[Question]] = relationship(
        "Question",
        back_populates="quiz",
        cascade="all, delete-orphan",
    )
    attempts: Mapped[list[QuizAttempt]] = relationship(
        "QuizAttempt",
        back_populates="quiz",
    )
