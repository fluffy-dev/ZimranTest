from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.attempt.enum import AttemptStatusEnum


@dataclass(slots=True, kw_only=True)
class QuizAttemptEntity:
    """Domain representation of a quiz attempt."""
    id: uuid.UUID
    quiz_id: uuid.UUID
    user_id: uuid.UUID
    status: AttemptStatusEnum
    score: int | None
    total_questions: int | None
    started_at: datetime
    updated_at: datetime
    completed_at: datetime | None


@dataclass(slots=True, kw_only=True)
class UserQuestionAnswerEntity:
    """Domain representation of a user's answer to a single question."""
    id: uuid.UUID
    attempt_id: uuid.UUID
    question_id: uuid.UUID
    answer_payload: dict[str, Any]
    is_correct: bool | None
    answered_at: datetime


@dataclass(slots=True, kw_only=True)
class UserRewardedQuestionEntity:
    """Domain representation of a rewarded question record."""
    user_id: uuid.UUID
    question_id: uuid.UUID
    quiz_id: uuid.UUID
    rewarded_at: datetime


@dataclass(slots=True, kw_only=True)
class OutboxEventEntity:
    """Domain representation of a transactional outbox event."""
    id: uuid.UUID
    event_type: str
    routing_key: str
    payload: dict[str, Any]
    created_at: datetime
    published_at: datetime | None
    attempts: int