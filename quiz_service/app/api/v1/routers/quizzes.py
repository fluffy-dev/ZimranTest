from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status

from app.dependencies.common import ILocale
from app.dependencies.services import IQuizService
from app.schemas.quiz import CreateQuizRequest, QuizDetailResponse, QuizListResponse

router = APIRouter(prefix="/quizzes", tags=["Quizzes"])


@router.get("", response_model=QuizListResponse, summary="List active quizzes (localized)")
async def list_quizzes(
    service: IQuizService,
    locale: ILocale,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> QuizListResponse:
    return await service.list_quizzes(locale=locale, page=page, page_size=page_size)


@router.get("/{quiz_id}", response_model=QuizDetailResponse, summary="Get quiz detail (localized)")
async def get_quiz(
    quiz_id: uuid.UUID,
    service: IQuizService,
    locale: ILocale,
) -> QuizDetailResponse:
    return await service.get_quiz(quiz_id=quiz_id, locale=locale)


@router.post(
    "",
    response_model=QuizDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a quiz with questions",
)
async def create_quiz(
    body: CreateQuizRequest,
    service: IQuizService,
) -> QuizDetailResponse:
    return await service.create_quiz(body)
