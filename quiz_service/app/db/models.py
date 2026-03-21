from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class QuestionType(str, Enum):
    SINGLE_CHOICE = "single_choice"
    FILL_GAP = "fill_gap"
    MULTIPLE_CHOICE = "multiple_choice"
    MATCHING = "matching"


class AttemptStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


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

    questions: Mapped[list[Question]] = relationship(
        "Question", back_populates="quiz", cascade="all, delete-orphan", lazy="selectin"
    )
    attempts: Mapped[list[QuizAttempt]] = relationship(
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
    answers: Mapped[list[UserQuestionAnswer]] = relationship(
        "UserQuestionAnswer", back_populates="question"
    )

    __table_args__ = (
        Index("idx_questions_quiz_id", "quiz_id"),
        Index("idx_questions_quiz_order", "quiz_id", "order_index"),
    )


class QuizAttempt(Base):
    """Tracks one user's attempt at a quiz."""

    __tablename__ = "quiz_attempts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    quiz_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quizzes.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=AttemptStatus.IN_PROGRESS, nullable=False
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
    answers: Mapped[list[UserQuestionAnswer]] = relationship(
        "UserQuestionAnswer", back_populates="attempt", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_quiz_attempts_user_id", "user_id"),
        Index("idx_quiz_attempts_quiz_id", "quiz_id"),
        Index("idx_quiz_attempts_user_quiz", "user_id", "quiz_id"),
    )


class UserQuestionAnswer(Base):
    """Stores a user's answer to one question within an attempt."""

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
        UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False
    )
    answer_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    answered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    attempt: Mapped[QuizAttempt] = relationship("QuizAttempt", back_populates="answers")
    question: Mapped[Question] = relationship("Question", back_populates="answers")

    __table_args__ = (Index("idx_user_question_answers_attempt_id", "attempt_id"),)


class UserRewardedQuestion(Base):
    """
    Records which questions a user has already been rewarded for answering correctly.
    Composite PK (user_id, question_id) provides natural idempotency — a user can
    only be rewarded once per question regardless of how many correct attempts they make.
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


class OutboxEvent(Base):
    """
    Transactional Outbox table.
    Events are written atomically with business data in the same DB transaction,
    then published to RabbitMQ by a background worker.
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
