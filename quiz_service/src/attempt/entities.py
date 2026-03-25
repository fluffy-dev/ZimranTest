from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import uuid


@dataclass(slots=True)
class QuizAttemptEntity:
    """Domain representation of a quiz attempt."""
    id: uuid.UUID
    quiz_id: uuid.UUID
    user_id: uuid.UUID
    status: str
    score: int | None
    total_questions: int | None
    started_at: Any
    completed_at: Any | None


@dataclass(slots=True)
class AnswerEntity:
    """Domain representation of a user's answer to a single question."""
    question_id: uuid.UUID
    answer_payload: dict[str, Any]
    is_correct: bool
