import uuid

from fastapi import APIRouter

from src.dependencies.common import IUserID
from src.attempt.dependencies.attempt_service import IAttemptService
from src.attempt.dto import AttemptStartResponseDTO, AttemptResultResponseDTO, SubmitAttemptDTO

router = APIRouter(prefix="/attempts", tags=["Attempts"])


@router.post("/start", response_model=AttemptStartResponseDTO, summary="Start a new attempt")
async def start_attempt(
    quiz_id: uuid.UUID,
    service: IAttemptService,
    user_id: IUserID,
) -> AttemptStartResponseDTO:
    """
    Initializes a new quiz attempt for the user.
    """
    return await service.start_attempt(quiz_id=quiz_id, user_id=user_id)


@router.post("/{attempt_id}/submit", response_model=AttemptResultResponseDTO, summary="Submit quiz attempt")
async def submit_attempt(
    attempt_id: uuid.UUID,
    body: SubmitAttemptDTO,
    service: IAttemptService,
    user_id: IUserID,
) -> AttemptResultResponseDTO:
    """
    Grades the attempt, awards coins if applicable, and triggers outbox events.
    """
    return await service.submit_attempt(
        attempt_id=attempt_id,
        user_id=user_id,
        request=body,
    )
