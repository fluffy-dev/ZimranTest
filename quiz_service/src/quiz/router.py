import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from src.dependencies.common import ILocale
from src.quiz.dependencies.service import IQuizService
from src.quiz.dto import (
    CreateQuestionDTO,
    CreateQuizDTO,
    EntityCreatedResponseDTO,
    QuizDetailResponseDTO,
    QuizListResponseDTO,
    UpdateQuizStatusDTO,
)

router = APIRouter(prefix="/quizzes", tags=["Quizzes"])


@router.get("", response_model=QuizListResponseDTO, status_code=status.HTTP_200_OK)
async def list_active_quizzes(
    service: IQuizService,
    locale: ILocale,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> QuizListResponseDTO:
    """Retrieves a paginated, localized catalogue of active quizzes.

    Args:
        service: The injected QuizService.
        locale: The requested language code extracted from headers.
        limit: The maximum number of records to return.
        offset: The number of records to skip.

    Returns:
        A paginated list of summary quiz items.
    """
    return await service.get_catalogue(locale=locale, limit=limit, offset=offset)


@router.get("/{quiz_id}", response_model=QuizDetailResponseDTO, status_code=status.HTTP_200_OK)
async def get_quiz_details(
    quiz_id: uuid.UUID,
    service: IQuizService,
    locale: ILocale,
) -> QuizDetailResponseDTO:
    """Retrieves the fully localized, sanitized structure of a specific quiz.

    Args:
        quiz_id: The UUID of the target quiz.
        service: The injected QuizService.
        locale: The requested language code extracted from headers.

    Returns:
        The detailed quiz configuration stripped of grading data.
    """
    return await service.get_quiz_for_attempt(quiz_id=quiz_id, locale=locale)


@router.post("", response_model=EntityCreatedResponseDTO, status_code=status.HTTP_201_CREATED)
async def create_new_quiz(
    dto: CreateQuizDTO,
    service: IQuizService,
) -> EntityCreatedResponseDTO:
    """Creates a new inactive quiz structure from a comprehensive payload.

    Args:
        dto: The creation payload containing localized text and optional questions.
        service: The injected QuizService.

    Returns:
        The generated UUID of the created quiz.
    """
    quiz_id = await service.create_quiz(dto=dto)
    return EntityCreatedResponseDTO(id=quiz_id)


@router.patch("/{quiz_id}/status", status_code=status.HTTP_204_NO_CONTENT)
async def update_quiz_status(
    quiz_id: uuid.UUID,
    dto: UpdateQuizStatusDTO,
    service: IQuizService,
) -> None:
    """Atomically updates the visibility status of a quiz.

    Args:
        quiz_id: The UUID of the target quiz.
        dto: The payload containing the new boolean state.
        service: The injected QuizService.
    """
    await service.set_quiz_active_status(quiz_id=quiz_id, is_active=dto.is_active)


@router.post(
    "/{quiz_id}/questions",
    response_model=EntityCreatedResponseDTO,
    status_code=status.HTTP_201_CREATED,
)
async def append_question(
    quiz_id: uuid.UUID,
    dto: CreateQuestionDTO,
    service: IQuizService,
) -> EntityCreatedResponseDTO:
    """Appends a newly configured question to an existing quiz.

    Args:
        quiz_id: The UUID of the parent quiz.
        dto: The configuration payload for the new question.
        service: The injected QuizService.

    Returns:
        The generated UUID of the created question.
    """
    question_id = await service.append_question(quiz_id=quiz_id, dto=dto)
    return EntityCreatedResponseDTO(id=question_id)


@router.put("/{quiz_id}/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_question(
    quiz_id: uuid.UUID,
    question_id: uuid.UUID,
    dto: CreateQuestionDTO,
    service: IQuizService,
) -> None:
    """Overwrites the localized text and payload configuration of an existing question.

    Args:
        quiz_id: The UUID of the parent quiz (used for semantic routing clarity).
        question_id: The UUID of the target question.
        dto: The updated configuration payload.
        service: The injected QuizService.
    """
    await service.update_question(question_id=question_id, dto=dto)


@router.delete("/{quiz_id}/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question(
    quiz_id: uuid.UUID,
    question_id: uuid.UUID,
    service: IQuizService,
) -> None:
    """Hard deletes a question from the parent quiz structure.

    Args:
        quiz_id: The UUID of the parent quiz (used for semantic routing clarity).
        question_id: The UUID of the target question to remove.
        service: The injected QuizService.
    """
    await service.delete_question(question_id=question_id)