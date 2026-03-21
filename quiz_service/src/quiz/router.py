import uuid

from fastapi import APIRouter, Query, status

from app.dependencies.common import ILocale
from src.quiz.dependencies.service import IQuizService
from src.quiz.dto import CreateQuizDTO, QuizDetailResponseDTO, QuizListResponseDTO

router = APIRouter(prefix="/quizzes", tags=["Quizzes"])


@router.get("", response_model=QuizListResponseDTO, summary="List active quizzes (localized)")
async def list_quizzes(
    service: IQuizService,
    locale: ILocale,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> QuizListResponseDTO:
    """
    Returns a list of all active quizzes.
    Localized based on the `Accept-Language` header.
    """
    return await service.list_quizzes(locale=locale, page=page, page_size=page_size)


@router.get("/{quiz_id}", response_model=QuizDetailResponseDTO, summary="Get quiz detail (localized)")
async def get_quiz(
    quiz_id: uuid.UUID,
    service: IQuizService,
    locale: ILocale,
) -> QuizDetailResponseDTO:
    """
    Returns the full details of a quiz by ID.
    Questions are localized and correct answer fields are stripped.
    """
    return await service.get_quiz(quiz_id=quiz_id, locale=locale)


@router.post(
    "",
    response_model=QuizDetailResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Create a quiz with questions",
)
async def create_quiz(
    body: CreateQuizDTO,
    service: IQuizService,
) -> QuizDetailResponseDTO:
    """
    Creates a basic quiz with a list of polymorphic questions.
    """
    return await service.create_quiz(body)
