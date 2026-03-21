from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


class AnswerItem(BaseModel):
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


class SubmitAttemptRequest(BaseModel):
    answers: list[AnswerItem] = Field(..., min_length=1)


class QuestionResultItem(BaseModel):
    question_id: uuid.UUID
    is_correct: bool
    was_already_rewarded: bool


class AttemptResultResponse(BaseModel):
    attempt_id: uuid.UUID
    score: int
    total_questions: int
    coins_awarded: int
    question_results: list[QuestionResultItem]


class AttemptStartResponse(BaseModel):
    attempt_id: uuid.UUID
    quiz_id: uuid.UUID
    user_id: uuid.UUID
