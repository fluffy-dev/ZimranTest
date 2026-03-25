from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from src.attempt.dependencies.attempt_service import IAttemptService
from src.attempt.dto import (
    AttemptStartResponseDTO,
    AttemptResultResponseDTO,
    SubmitAttemptDTO,
    AutoSaveRequestDTO,
)
from src.dependencies.common import IUserID

router = APIRouter(prefix="/attempts", tags=["Attempts"])


@router.post(
    "/{quiz_id}/start",
    response_model=AttemptStartResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Start a new quiz attempt",
)
async def start_attempt(
    quiz_id: uuid.UUID,
    user_id: IUserID,
    service: IAttemptService,
) -> AttemptStartResponseDTO:
    """
    Creates a new attempt record for the given quiz and user.
    """
    return await service.start_attempt(quiz_id=quiz_id, user_id=user_id)


@router.put(
    "/{attempt_id}/answers",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Auto-save a draft answer",
)
async def auto_save_answer(
    attempt_id: uuid.UUID,
    user_id: IUserID,
    request: AutoSaveRequestDTO,
    service: IAttemptService,
) -> None:
    """
    Idempotently saves a draft answer without grading it.
    Used for preventing data loss during an active attempt.
    """
    await service.auto_save_answer(
        attempt_id=attempt_id,
        user_id=user_id,
        request=request
    )


@router.post(
    "/{attempt_id}/submit",
    response_model=AttemptResultResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Submit and grade an attempt",
)
async def submit_attempt(
    attempt_id: uuid.UUID,
    user_id: IUserID,
    request: SubmitAttemptDTO,
    service: IAttemptService,
) -> AttemptResultResponseDTO:
    """
    Finalizes the attempt, grades all answers, and processes rewards.
    """
    return await service.submit_attempt(
        attempt_id=attempt_id,
        user_id=user_id,
        request=request
    )


@router.post(
    "/{attempt_id}/abandon",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Explicitly abandon an attempt",
)
async def abandon_attempt(
    attempt_id: uuid.UUID,
    user_id: IUserID,
    service: IAttemptService,
) -> None:
    """
    Marks an active attempt as abandoned. No further modifications will be allowed.
    """
    await service.abandon_attempt(attempt_id=attempt_id, user_id=user_id)