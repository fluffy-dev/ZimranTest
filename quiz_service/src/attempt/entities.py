from src.attempt.enum import AttemptStatusEnum
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class QuizAttemptEntity:
    """
    Domain entity representing a user's attempt at a quiz.
    Decoupled from the database model, used within the service layer.
    """
    id: uuid.UUID
    quiz_id: uuid.UUID
    user_id: uuid.UUID
    status: AttemptStatusEnum
    score: int | None
    total_questions: int | None
    started_at: datetime
    completed_at: datetime | None


@dataclass
class OutboxEventEntity:
    """
    Domain entity representing a transactional outbox event.
    Contains the event metadata and JSON-serializable payload.
    """
    id: uuid.UUID
    event_type: str
    routing_key: str
    payload: dict[str, Any]
    created_at: datetime
    published_at: datetime | None
    attempts: int
