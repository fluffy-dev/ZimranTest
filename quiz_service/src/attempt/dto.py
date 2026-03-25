import uuid
from typing import Any

from pydantic import BaseModel, Field


import uuid
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class SingleChoicePayload(BaseModel):
    """Strict schema for a single choice answer."""
    question_type: Literal["single_choice"]
    selected_id: uuid.UUID


class MultipleChoicePayload(BaseModel):
    """Strict schema for a multiple choice answer."""
    question_type: Literal["multiple_choice"]
    selected_ids: list[uuid.UUID] = Field(..., min_length=1)


class FillGapPayload(BaseModel):
    """Strict schema for a fill-in-the-gap answer."""
    question_type: Literal["fill_gap"]
    answer: str = Field(..., min_length=1, json_schema_extra={"strip_whitespace": True})


class MatchingPair(BaseModel):
    """Strict schema for a single matching pair."""
    pair_id: uuid.UUID
    matched_pair_id: uuid.UUID


class MatchingPayload(BaseModel):
    """Strict schema for a matching question answer."""
    question_type: Literal["matching"]
    pairs: list[MatchingPair] = Field(..., min_length=1)



StrictAnswerPayload: type[SingleChoicePayload | MultipleChoicePayload | FillGapPayload | MatchingPayload] = Annotated[
    Union[
        SingleChoicePayload, 
        MultipleChoicePayload, 
        FillGapPayload, 
        MatchingPayload
    ],
    Field(discriminator="question_type")
]


class AnswerItemDTO(BaseModel):
    """
    DTO for a single question answer. 
    Now strictly typed—zero raw dicts allowed.
    """
    question_id: uuid.UUID
    answer_payload: StrictAnswerPayload


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

class AutoSaveRequestDTO(BaseModel):
    """
    DTO for auto-saving a single draft answer during an active attempt.
    """
    answer: AnswerItemDTO
