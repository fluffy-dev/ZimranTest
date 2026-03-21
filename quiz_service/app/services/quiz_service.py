from __future__ import annotations

import uuid
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings
from app.dependencies.common import IRedis
from app.dependencies.repositories import IQuizRepository
from app.schemas.quiz import QuizDetailResponse, QuizListResponse, CreateQuizRequest
from shared.exceptions import NotFoundException
from shared.logging import get_logger

logger = get_logger(__name__)


class QuizService:
    """Manages quiz CRUD and localized retrieval. Instantiated by deps.py factory."""

    def __init__(self, quiz_repo: IQuizRepository, redis: IRedis) -> None:
        self._repo = quiz_repo
        self._redis = redis

    def _localize(self, jsonb_field: dict[str, Any] | None, locale: str) -> str | None:
        if jsonb_field is None:
            return None
        key = locale.lower().strip()
        return jsonb_field.get(key) or jsonb_field.get("en") or next(iter(jsonb_field.values()), None)

    async def list_quizzes(self, locale: str, page: int = 1, page_size: int = 20) -> QuizListResponse:
        cache_key = f"quizzes:list:{locale}:{page}:{page_size}"
        cached = await self._redis.get(cache_key)
        if cached:
            return QuizListResponse.model_validate_json(cached)

        offset = (page - 1) * page_size
        quizzes = await self._repo.get_all_active(limit=page_size, offset=offset)
        total = await self._repo.count_active()

        items = [
            {
                "id": str(q.id),
                "title": self._localize(q.title, locale),
                "description": self._localize(q.description, locale),
                "question_count": len(q.questions),
            }
            for q in quizzes
        ]
        response = QuizListResponse(items=items, total=total, page=page, page_size=page_size)
        await self._redis.setex(cache_key, settings.QUIZ_CACHE_TTL, response.model_dump_json())
        return response

    async def get_quiz(self, quiz_id: uuid.UUID, locale: str) -> QuizDetailResponse:
        cache_key = f"quizzes:{quiz_id}:{locale}"
        cached = await self._redis.get(cache_key)
        if cached:
            return QuizDetailResponse.model_validate_json(cached)

        quiz = await self._repo.get_by_id(quiz_id)
        if quiz is None or not quiz.is_active:
            raise NotFoundException(f"Quiz {quiz_id} not found.")

        questions_out = []
        for q in sorted(quiz.questions, key=lambda x: x.order_index):
            localized_payload = self._localize_question_payload(q.payload, q.type, locale)
            questions_out.append({
                "id": str(q.id),
                "type": q.type,
                "order_index": q.order_index,
                "text": self._localize(q.text, locale),
                "payload": localized_payload,
            })

        response = QuizDetailResponse(
            id=str(quiz.id),
            title=self._localize(quiz.title, locale),
            description=self._localize(quiz.description, locale),
            questions=questions_out,
        )
        await self._redis.setex(cache_key, settings.QUIZ_CACHE_TTL, response.model_dump_json())
        return response

    def _localize_question_payload(self, payload: dict[str, Any], question_type: str, locale: str) -> dict[str, Any]:
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

    async def create_quiz(self, request: CreateQuizRequest) -> QuizDetailResponse:
        quiz = await self._repo.create(title=request.title, description=request.description)
        for i, q_req in enumerate(request.questions):
            await self._repo.add_question(
                quiz_id=quiz.id, question_type=q_req.type,
                text=q_req.text, payload=q_req.payload, order_index=i,
            )
        await self._invalidate_list_cache()
        return await self.get_quiz(quiz.id, locale="en")

    async def _invalidate_list_cache(self) -> None:
        async for key in self._redis.scan_iter("quizzes:list:*"):
            await self._redis.delete(key)
