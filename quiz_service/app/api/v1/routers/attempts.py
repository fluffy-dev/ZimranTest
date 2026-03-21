from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.dependencies.common import IUserID
from app.dependencies.services import IAttemptService
from app.schemas.attempt import AttemptResultResponse, AttemptStartResponse, SubmitAttemptRequest

router = APIRouter(tags=["Attempts"])


@router.post(
    "/quizzes/{quiz_id}/attempts",
    response_model=AttemptStartResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a quiz attempt",
)
async def start_attempt(
    quiz_id: uuid.UUID,
    user_id: IUserID,
    service: IAttemptService,
) -> AttemptStartResponse:
    attempt = await service.start_attempt(quiz_id=quiz_id, user_id=user_id)
    return AttemptStartResponse(
        attempt_id=attempt.id,
        quiz_id=attempt.quiz_id,
        user_id=attempt.user_id,
    )


@router.post(
    "/attempts/{attempt_id}/submit",
    response_model=AttemptResultResponse,
    summary="Submit all answers for an attempt",
)
async def submit_attempt(
    attempt_id: uuid.UUID,
    body: SubmitAttemptRequest,
    user_id: IUserID,
    service: IAttemptService,
) -> AttemptResultResponse:
    return await service.submit_attempt(
        attempt_id=attempt_id, user_id=user_id, request=body
    )


@router.get(
    "/attempts/{attempt_id}/result",
    summary="Get attempt result",
)
async def get_attempt_result(
    attempt_id: uuid.UUID,
    user_id: IUserID,
    service: IAttemptService,
) -> dict:
    attempt = await service.get_attempt_result(attempt_id=attempt_id)
    correct = sum(1 for a in attempt.answers if a.is_correct)
    return {
        "attempt_id": attempt.id,
        "score": attempt.score or correct,
        "total_questions": attempt.total_questions or len(attempt.answers),
        "coins_awarded": 0,
        "question_results": [
            {"question_id": a.question_id, "is_correct": a.is_correct, "was_already_rewarded": False}
            for a in attempt.answers
        ],
    }
