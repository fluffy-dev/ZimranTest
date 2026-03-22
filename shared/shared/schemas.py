from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class EventEnvelope(BaseModel):
    """Base envelope for all domain events published to RabbitMQ."""

    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    event_type: str
    schema_version: str = "1.0"
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    payload: dict[str, Any]


class QuizRewardPayload(BaseModel):
    user_id: uuid.UUID
    quiz_id: uuid.UUID
    attempt_id: uuid.UUID
    newly_rewarded_question_ids: list[uuid.UUID]
    coins_to_award: int


class QuizRewardEvent(EventEnvelope):
    event_type: str = "quiz.questions.rewarded"
    payload: QuizRewardPayload  # type: ignore[assignment]
