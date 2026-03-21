from typing import Any
from pydantic import BaseModel, Field


class QuizSummaryItemDTO(BaseModel):
    id: str
    title: str | None
    description: str | None
    question_count: int


class QuizListResponseDTO(BaseModel):
    items: list[QuizSummaryItemDTO]
    total: int
    page: int
    page_size: int


class QuestionOutDTO(BaseModel):
    id: str
    type: str
    order_index: int
    text: str | None
    payload: dict[str, Any]  # correct answers stripped server-side


class QuizDetailResponseDTO(BaseModel):
    id: str
    title: str | None
    description: str | None
    questions: list[QuestionOutDTO]


class CreateQuestionDTO(BaseModel):
    type: str = Field(..., description="single_choice | fill_gap | multiple_choice | matching")
    text: dict[str, str] = Field(..., description='Localized text: {"en": "...", "de": "..."}')
    payload: dict[str, Any] = Field(
        ...,
        description=(
            "Type-specific payload."
        ),
    )


class CreateQuizDTO(BaseModel):
    title: dict[str, str] = Field(..., description='Localized: {"en": "Title", "de": "Titel"}')
    description: dict[str, str] | None = None
    questions: list[CreateQuestionDTO] = Field(default_factory=list)
