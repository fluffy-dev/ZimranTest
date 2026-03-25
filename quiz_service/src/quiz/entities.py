from dataclasses import dataclass, field
from typing import Any
import uuid


@dataclass(slots=True)
class QuestionEntity:
    """Domain representation of a quiz question."""

    id: uuid.UUID
    type: str
    order_index: int
    text: dict[str, Any]
    payload: dict[str, Any]


@dataclass(slots=True)
class QuizEntity:
    """Domain representation of a quiz."""

    id: uuid.UUID
    title: dict[str, Any]
    description: dict[str, Any] | None
    is_active: bool
    question_count: int = 0
    questions: list[QuestionEntity] = field(default_factory=list)