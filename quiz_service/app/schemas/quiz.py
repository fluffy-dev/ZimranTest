from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


class QuizSummaryItem(BaseModel):
    id: str
    title: str | None
    description: str | None
    question_count: int


class QuizListResponse(BaseModel):
    items: list[QuizSummaryItem]
    total: int
    page: int
    page_size: int


class QuestionOut(BaseModel):
    id: str
    type: str
    order_index: int
    text: str | None
    payload: dict[str, Any]  # correct answers stripped server-side


class QuizDetailResponse(BaseModel):
    id: str
    title: str | None
    description: str | None
    questions: list[QuestionOut]


class CreateQuestionRequest(BaseModel):
    type: str = Field(..., description="single_choice | fill_gap | multiple_choice | matching")
    text: dict[str, str] = Field(..., description='Localized text: {"en": "...", "de": "..."}')
    payload: dict[str, Any] = Field(
        ...,
        description=(
            "Type-specific payload. "
            "single_choice: {options: [...], correct_id: str}; "
            "fill_gap: {correct_answers: [str]}; "
            "multiple_choice: {options: [...], correct_ids: [str]}; "
            "matching: {pairs: [{id, left, right}]}"
        ),
    )


class CreateQuizRequest(BaseModel):
    title: dict[str, str] = Field(..., description='Localized: {"en": "Title", "de": "Titel"}')
    description: dict[str, str] | None = None
    questions: list[CreateQuestionRequest] = Field(default_factory=list)
