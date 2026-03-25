import uuid

from typing import Any
from pydantic import BaseModel, Field


class QuizListItemDTO(BaseModel):
    """
    DTO for a single quiz item in a list results.
    Provides brief metadata and question count.
    """
    id: str
    title: str | None
    description: str | None
    question_count: int


class QuizListResponseDTO(BaseModel):
    """
    DTO for the paginated list of quizzes response.
    Includes items and pagination metadata.
    """
    items: list[QuizListItemDTO]
    total: int
    page: int
    page_size: int


class QuestionDetailDTO(BaseModel):
    """
    DTO for detailed information about a single question.
    Contains the localized text and payload for display.
    """
    id: str
    type: str
    order_index: int
    text: str | None
    payload: dict[str, Any]


class QuizDetailResponseDTO(BaseModel):
    """
    DTO for the full localized details of a quiz.
    Includes all questions and metadata.
    """
    id: str
    title: str | None
    description: str | None
    questions: list[QuestionDetailDTO]


class CreateQuestionDTO(BaseModel):
    """
    DTO for creating a new question within a create-quiz request.
    Includes type, localized text, and answer-key payload.
    """
    type: str = Field(..., description="single_choice | fill_gap | multiple_choice | matching")
    text: dict[str, str] = Field(..., description='Localized text: {"en": "...", "de": "..."}')
    payload: dict[str, Any] = Field(
        ...,
        description=(
            "Type-specific payload."
        ),
    )


class CreateQuizDTO(BaseModel):
    """
    DTO for creating a new quiz and its associated questions.
    """
    title: dict[str, str] = Field(..., description='Localized: {"en": "Title", "de": "Titel"}')
    description: dict[str, str] | None = None
    questions: list[CreateQuestionDTO] = Field(default_factory=list)


class UpdateQuizStatusDTO(BaseModel):
    """Data Transfer Object for explicitly updating a quiz's activation status."""
    is_active: bool = Field(..., description="The boolean visibility state to apply.")


class EntityCreatedResponseDTO(BaseModel):
    """Standardized Data Transfer Object for creation endpoints returning a UUID."""
    id: uuid.UUID = Field(..., description="The generated unique identifier.")