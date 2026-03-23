import uuid
from typing import Any

from pydantic import BaseModel, Field


class AnswerItemDTO(BaseModel):
    """
    DTO for a single question answer in a submission.
    Contains the question ID and the answer payload.
    """
    question_id: uuid.UUID
    answer_payload: dict[str, Any] = Field(
        ...,
        description=(
            "Type-specific answer. "
            "single_choice: {selected_id: str}; "
            "fill_gap: {answer: str}; "
            "multiple_choice: {selected_ids: [str]}; "
            "matching: {pairs: [{pair_id: str, matched_pair_id: str}]}"
        ),
    )


class SubmitAttemptDTO(BaseModel):
    """
    DTO for submitting a whole quiz attempt.
    Contains a list of answers and expects at least one answer.
    """
    answers: list[AnswerItemDTO] = Field(..., min_length=1)


class QuestionResultItemDTO(BaseModel):
    """
    DTO for the result of a single question within a submission.
    Indicates correctness and whether a reward was newly granted.
    """
    question_id: uuid.UUID
    is_correct: bool
    was_already_rewarded: bool


class AttemptResultResponseDTO(BaseModel):
    """
    DTO for the overall result of a submitted quiz attempt.
    Includes score, total questions, coins awarded, and detailed results.
    """
    attempt_id: uuid.UUID
    score: int
    total_questions: int
    coins_awarded: int
    question_results: list[QuestionResultItemDTO]


class AttemptStartResponseDTO(BaseModel):
    """
    DTO returned when a new quiz attempt is successfully started.
    Provides the unique identifiers for the attempt, quiz, and user.
    """
    attempt_id: uuid.UUID
    quiz_id: uuid.UUID
    user_id: uuid.UUID
