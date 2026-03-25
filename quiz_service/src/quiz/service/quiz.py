from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from src.uow import IUnitOfWork
from src.quiz.repositories.cached_quiz import CachingQuizRepository
from src.quiz.dto import QuizDetailResponseDTO, QuizListResponseDTO, QuizListItemDTO, QuestionDetailDTO
from src.libs.localization import localize_field, localize_question_payload
from src.dependencies.common import IRedis
from shared.exceptions import NotFoundException
from shared.logging import get_logger

if TYPE_CHECKING:
    from src.quiz.dto import CreateQuizDTO

logger = get_logger(__name__)


class QuizService:
    """Business logic layer for managing quizzes.
    
    Returns DTOs directly, mirroring the balance_service architectural style.
    """

    def __init__(self, uow: IUnitOfWork, redis: IRedis) -> None:
        """Initializes the service with Unit of Work and Redis client.

        Args:
            uow: Database Unit of Work instance.
            redis: Redis client for caching.
        """
        self._uow = uow
        self._repo = CachingQuizRepository(uow.quizzes, redis)

    async def list_quizzes(self, locale: str, page: int = 1, page_size: int = 20) -> QuizListResponseDTO:
        """Retrieves a paginated, localized list of active quizzes.

        Args:
            locale: Language code for localization.
            page: Page number to retrieve.
            page_size: Number of items per page.

        Returns:
            QuizListResponseDTO: Paginated result set.
        """
        offset = (page - 1) * page_size
        quizzes = await self._repo.get_all_active(limit=page_size, offset=offset)
        total = await self._repo.count_active()
        
        items = [
            QuizListItemDTO(
                id=str(q.id),
                title=localize_field(q.title, locale),
                description=localize_field(q.description, locale),
                question_count=len(q.questions),
            )
            for q in quizzes
        ]
        
        return QuizListResponseDTO(items=items, total=total, page=page, page_size=page_size)

    async def get_quiz(self, quiz_id: uuid.UUID, locale: str) -> QuizDetailResponseDTO:
        """Retrieves localized details for a specific quiz.

        Args:
            quiz_id: Unique identifier for the quiz.
            locale: Language code for localization.

        Returns:
            QuizDetailResponseDTO: Full localized quiz details.

        Raises:
            NotFoundException: If the quiz is missing or inactive.
        """
        quiz = await self._repo.get_by_id(quiz_id)
        if quiz is None or not quiz.is_active:
            raise NotFoundException(f"Quiz {quiz_id} not found.")
            
        questions_out = [
            QuestionDetailDTO(
                id=str(q.id),
                type=q.type,
                order_index=q.order_index,
                text=localize_field(q.text, locale),
                payload=localize_question_payload(q.payload, q.type, locale),
            )
            for q in sorted(quiz.questions, key=lambda x: x.order_index)
        ]

        return QuizDetailResponseDTO(
            id=str(quiz.id),
            title=localize_field(quiz.title, locale),
            description=localize_field(quiz.description, locale),
            questions=questions_out,
        )

    async def create_quiz(self, request: CreateQuizDTO) -> QuizDetailResponseDTO:
        """Creates a new quiz and returns its English-localized detail.

        Args:
            request: DTO containing quiz and question metadata.

        Returns:
            QuizDetailResponseDTO: Newly created quiz in English.
        """
        async with self._uow:
            quiz = await self._uow.quizzes.create(title=request.title, description=request.description)
            for i, q_req in enumerate(request.questions):
                await self._uow.quizzes.add_question(
                    quiz_id=quiz.id, 
                    question_type=q_req.type,
                    text=q_req.text, 
                    payload=q_req.payload, 
                    order_index=i,
                )
            await self._uow.commit()

        await self._repo.invalidate_cache() 
        logger.info("Quiz created", quiz_id=str(quiz.id))
        
        return await self.get_quiz(quiz_id=quiz.id, locale="en")
