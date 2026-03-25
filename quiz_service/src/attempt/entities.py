from __future__ import annotations

import uuid

from typing import Any
from datetime import datetime
from dataclasses import dataclass


@dataclass(slots=True)
class QuizAttemptEntity:
    """Domain representation of a quiz attempt."""
    id: uuid.UUID
    quiz_id: uuid.UUID
    user_id: uuid.UUID
    status: str
    score: int | None
    total_questions: int | None
    started_at: datetime
    updated_at: datetime
    completed_at: datetime | None


@dataclass(slots=True)
class AnswerEntity:
    """Domain representation of a user's answer to a single question."""
    question_id: uuid.UUID
    answer_payload: dict[str, Any]
    is_correct: bool | None