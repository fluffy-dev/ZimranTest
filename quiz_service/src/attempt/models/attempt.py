import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
    Enum as SQLEnum,
    CheckConstraint
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.libs.base_model import Base
from src.quiz.models.quiz import Question, Quiz
from src.attempt.enum import AttemptStatusEnum


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


class UserQuestionAnswer(Base):
    """
    SQLAlchemy model storing a user's specific answer to a question within an attempt.
    Captures the response payload and correctness.
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
