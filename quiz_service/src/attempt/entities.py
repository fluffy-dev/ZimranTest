import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class QuizAttemptEntity:
    """Domain representation of a user's attempt at a quiz."""
    id: uuid.UUID
    quiz_id: uuid.UUID
    user_id: uuid.UUID
    status: str
    score: int | None
    total_questions: int | None
    started_at: datetime
    completed_at: datetime | None


@dataclass
class OutboxEventEntity:
    """Domain representation of a transactional outbox event."""
    id: uuid.UUID
    event_type: str
    routing_key: str
    payload: dict[str, Any]
    created_at: datetime
    published_at: datetime | None
    attempts: int
