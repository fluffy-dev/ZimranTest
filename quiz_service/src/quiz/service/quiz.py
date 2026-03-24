from __future__ import annotations

import uuid
from typing import Any

from src.uow import IUnitOfWork
from src.quiz.dependencies.repository import IQuizRepository
from src.quiz.dto import QuizDetailResponseDTO, QuizListResponseDTO, CreateQuizDTO
from src.dependencies.common import IRedis
from src.config.redis import settings as redis_settings
from shared.exceptions import NotFoundException
from shared.logging import get_logger

logger = get_logger(__name__)


class QuizService:
    """Manages quiz creation, retrieval, and localization.
    Handles caching via Redis for optimized performance."""

    def __init__(
        self,
        quiz_repo: IQuizRepository,
        redis: IRedis,
        uow: IUnitOfWork,
    ) -> None:
        """Initializes the QuizService.

        Args:
            quiz_repo: Repository for read-only quiz data access.
            redis: Redis client for caching.
            uow: Unit of Work for write operations.
        """
        self._repo = quiz_repo
        self._redis = redis
        self._uow = uow

    def _localize(self, jsonb_field: dict[str, Any] | None, locale: str) -> str | None:
        """Extracts the value for a specific locale from a JSONB field.
        Falls back to 'en' or the first available value if the requested locale is missing."""
        if jsonb_field is None:
            return None
        key = locale.lower().strip()
        return jsonb_field.get(key) or jsonb_field.get("en") or next(iter(jsonb_field.values()), None)

    async def list_quizzes(self, locale: str, page: int = 1, page_size: int = 20) -> QuizListResponseDTO:
        """Retrieves a paginated list of active quizzes, localized to the requested language.

        Args:
            locale: The ISO language code (e.g., 'en', 'es').
            page: The page number to retrieve.
            page_size: Number of items per page.

        Returns:
            QuizListResponseDTO: Localized list of quizzes and pagination metadata.
        """
        cache_key = f"quizzes:list:{locale}:{page}:{page_size}"
        cached = await self._redis.get(cache_key)
        if cached:
            return QuizListResponseDTO.model_validate_json(cached)

        offset = (page - 1) * page_size
        quizzes = await self._repo.get_all_active(limit=page_size, offset=offset)
        total = await self._repo.count_active()

        items = [self._map_to_list_item(q, locale) for q in quizzes]

        response = QuizListResponseDTO(items=items, total=total, page=page, page_size=page_size)
        await self._redis.setex(cache_key, redis_settings.quiz_cache_ttl, response.model_dump_json())
        return response

    def _map_to_list_item(self, quiz, locale: str) -> dict[str, Any]:
        """Maps a QuizEntity to a dictionary suitable for QuizListResponseDTO."""
        return {
            "id": str(quiz.id),
            "title": self._localize(quiz.title, locale),
            "description": self._localize(quiz.description, locale),
            "question_count": len(quiz.questions),
        }

    async def get_quiz(self, quiz_id: uuid.UUID, locale: str) -> QuizDetailResponseDTO:
        """Retrieves detailed information for a specific quiz, including localized questions.

        Args:
            quiz_id: The unique identifier of the quiz.
            locale: The ISO language code for localization.

        Returns:
            QuizDetailResponseDTO: Full quiz details with localized content.

        Raises:
            NotFoundException: If the quiz is not found or is inactive.
        """
        cache_key = f"quizzes:{quiz_id}:{locale}"
        cached = await self._redis.get(cache_key)
        if cached:
            return QuizDetailResponseDTO.model_validate_json(cached)

        quiz = await self._repo.get_by_id(quiz_id)
        if quiz is None or not quiz.is_active:
            raise NotFoundException(f"Quiz {quiz_id} not found.")

        questions_out = [
            self._map_to_question_detail(q, locale)
            for q in sorted(quiz.questions, key=lambda x: x.order_index)
        ]

        response = QuizDetailResponseDTO(
            id=str(quiz.id),
            title=self._localize(quiz.title, locale),
            description=self._localize(quiz.description, locale),
            questions=questions_out,
        )
        await self._redis.setex(cache_key, redis_settings.quiz_cache_ttl, response.model_dump_json())
        return response

    def _map_to_question_detail(self, question, locale: str) -> dict[str, Any]:
        """Maps a QuestionEntity to a localized dictionary for QuizDetailResponseDTO."""
        return {
            "id": str(question.id),
            "type": question.type,
            "order_index": question.order_index,
            "text": self._localize(question.text, locale),
            "payload": self._localize_question_payload(question.payload, question.type, locale),
        }

    def _localize_question_payload(self, payload: dict[str, Any], question_type: str, locale: str) -> dict[str, Any]:
        """Localizes the content of a question payload and strips sensitive correct-answer data."""
        import copy
        p = copy.deepcopy(payload)

        if question_type in ("single_choice", "multiple_choice"):
            p.pop("correct_id", None)
            p.pop("correct_ids", None)
            for opt in p.get("options", []):
                opt["text"] = self._localize(opt.get("text", {}), locale) or ""
        elif question_type == "fill_gap":
            p.pop("correct_answers", None)
        elif question_type == "matching":
            for pair in p.get("pairs", []):
                pair["left"] = self._localize(pair.get("left", {}), locale) or ""
                pair["right"] = self._localize(pair.get("right", {}), locale) or ""
        return p

    async def create_quiz(self, request: CreateQuizDTO) -> QuizDetailResponseDTO:
        """Creates a new quiz along with its associated questions atomically.

        Uses the Unit of Work to ensure the quiz and all questions are
        persisted in a single transaction.

        Args:
            request: DTO containing the quiz and question details.

        Returns:
            QuizDetailResponseDTO: The newly created quiz details (localized to 'en').
        """
        async with self._uow:
            quiz = await self._uow.quizzes.create(
                title=request.title, description=request.description
            )
            for i, q_req in enumerate(request.questions):
                await self._uow.quizzes.add_question(
                    quiz_id=quiz.id,
                    question_type=q_req.type,
                    text=q_req.text,
                    payload=q_req.payload,
                    order_index=i,
                )
            await self._uow.commit()

        await self._invalidate_list_cache()
        return await self.get_quiz(quiz.id, locale="en")

    async def _invalidate_list_cache(self) -> None:
        """Invalidates all cached quiz lists in Redis."""
        async for key in self._redis.scan_iter("quizzes:list:*"):
            await self._redis.delete(key)
