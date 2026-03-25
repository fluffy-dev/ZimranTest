from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from typing import Any

from redis.asyncio import Redis

from src.config.redis import settings as redis_settings
from src.quiz.entities import QuestionEntity, QuizEntity
from src.quiz.enum import QuestionType
from src.quiz.repositories.quiz import QuizRepository


class CachingQuizRepository:
    """Decorator for QuizRepository that provides transparent Redis caching.

    Enforces read-through caching for query operations and cache invalidation
    for mutative operations, ensuring data consistency while optimizing read latency.
    """

    def __init__(self, repo: QuizRepository, redis: Redis) -> None:
        """Initializes the caching decorator.

        Args:
            repo: The underlying SQLAlchemy QuizRepository.
            redis: The asynchronous Redis client instance.
        """
        self._repo = repo
        self._redis = redis

    async def get_by_id(self, quiz_id: uuid.UUID) -> QuizEntity | None:
        """Retrieves a quiz by ID, utilizing a granular entity cache.

        Args:
            quiz_id: The UUID of the quiz.

        Returns:
            The QuizEntity if found, otherwise None.
        """
        cache_key = f"quiz:entity:{quiz_id}"
        cached = await self._redis.get(cache_key)

        if cached:
            try:
                data = json.loads(cached)
                return self._deserialize_quiz(data)
            except Exception:
                pass

        entity = await self._repo.get_by_id(quiz_id)

        if entity:
            serialized = json.dumps(asdict(entity), default=str)
            await self._redis.setex(cache_key, redis_settings.quiz_cache_ttl, serialized)

        return entity

    async def get_all_active(self, limit: int, offset: int) -> list[QuizEntity]:
        """Retrieves a paginated list of active quizzes from cache or database.

        Args:
            limit: The maximum number of records.
            offset: The number of records to skip.

        Returns:
            A list of active QuizEntity objects.
        """
        cache_key = f"quizzes:list:active:{limit}:{offset}"
        cached = await self._redis.get(cache_key)

        if cached:
            try:
                data = json.loads(cached)
                return [self._deserialize_quiz(q) for q in data]
            except Exception:
                pass

        entities = await self._repo.get_all_active(limit, offset)

        if entities:
            serialized = json.dumps([asdict(q) for q in entities], default=str)
            await self._redis.setex(cache_key, redis_settings.quiz_cache_ttl, serialized)

        return entities

    async def count_active(self) -> int:
        """Retrieves the total count of active quizzes, utilizing cache.

        Returns:
            The integer count of active quizzes.
        """
        cache_key = "quizzes:count:active"
        cached = await self._redis.get(cache_key)

        if cached:
            try:
                return int(cached)
            except ValueError:
                pass

        count = await self._repo.count_active()
        await self._redis.setex(cache_key, redis_settings.quiz_cache_ttl, str(count))

        return count

    async def add(self, entity: QuizEntity) -> None:
        """Persists a new quiz and invalidates list caches.

        Args:
            entity: The QuizEntity to persist.
        """
        await self._repo.add(entity)
        await self._invalidate_lists()

    async def set_active_status(self, quiz_id: uuid.UUID, is_active: bool) -> bool:
        """Updates the active status of a quiz and invalidates relevant caches.

        Args:
            quiz_id: The UUID of the quiz to update.
            is_active: The boolean status to apply.

        Returns:
            True if the record was updated, False if not found.
        """
        updated = await self._repo.set_active_status(quiz_id, is_active)
        if updated:
            await self._redis.delete(f"quiz:entity:{quiz_id}")
            await self._invalidate_lists()
        return updated

    async def update(self, entity: QuizEntity) -> bool:
        """Updates a quiz and invalidates its specific cache and list caches.

        Args:
            entity: The fully updated QuizEntity.

        Returns:
            True if the record was updated, False if not found.
        """
        updated = await self._repo.update(entity)
        if updated:
            await self._redis.delete(f"quiz:entity:{entity.id}")
            await self._invalidate_lists()
        return updated

    async def _invalidate_lists(self) -> None:
        """Clears all paginated list and count caches for quizzes."""
        await self._redis.delete("quizzes:count:active")
        async for key in self._redis.scan_iter("quizzes:list:*"):
            await self._redis.delete(key)

    def _deserialize_quiz(self, data: dict[str, Any]) -> QuizEntity:
        """Reconstructs a QuizEntity from a dictionary payload.

        Args:
            data: The deserialized JSON dictionary.

        Returns:
            A strictly typed QuizEntity.
        """
        questions = [
            QuestionEntity(
                id=uuid.UUID(q["id"]),
                type=QuestionType(q["type"]),
                order_index=q["order_index"],
                text=q["text"],
                payload=q["payload"],
            )
            for q in data.get("questions", [])
        ]

        return QuizEntity(
            id=uuid.UUID(data["id"]),
            title=data["title"],
            description=data["description"],
            is_active=data["is_active"],
            question_count=data.get("question_count", len(questions)),
            questions=questions,
        )

