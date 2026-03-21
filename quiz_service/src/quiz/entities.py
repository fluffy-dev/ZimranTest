from dataclasses import dataclass
from typing import Any
import uuid


@dataclass
class QuestionEntity:
    """Domain entity representing a Quiz Question."""

    id: uuid.UUID
    type: str
    order_index: int
    text: dict[str, Any]
    payload: dict[str, Any]


@dataclass
class QuizEntity:
    """Domain entity representing a Quiz."""

    id: uuid.UUID
    title: dict[str, Any]
    description: dict[str, Any] | None
    is_active: bool
    questions: list[QuestionEntity]
