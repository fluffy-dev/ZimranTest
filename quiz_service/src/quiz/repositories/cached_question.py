from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from typing import Any

from redis.asyncio import Redis

from src.config.redis import settings as redis_settings
from src.quiz.entities import QuestionEntity
from src.quiz.enum import QuestionType
from src.quiz.repositories.question import QuestionRepository


class CachingQuestionRepository:
    """Decorator for QuestionRepository that provides transparent Redis caching.

    Handles localized question caching and aggressive invalidation of parent quiz
    caches to maintain structural consistency.
    """

    def __init__(self, repo: QuestionRepository, redis: Redis) -> None:
        """Initializes the caching decorator.

        Args:
            repo: The underlying SQLAlchemy QuestionRepository.
            redis: The asynchronous Redis client instance.
        """
        self._repo = repo
        self._redis = redis

    async def get_by_id(self, question_id: uuid.UUID) -> QuestionEntity | None:
        """Retrieves a question by ID, utilizing cache.

        Args:
            question_id: The UUID of the question.

        Returns:
            The QuestionEntity if found, otherwise None.
        """
        cache_key = f"question:entity:{question_id}"
        cached = await self._redis.get(cache_key)

        if cached:
            try:
                data = json.loads(cached)
                return self._deserialize_question(data)
            except Exception:
                pass

        entity = await self._repo.get_by_id(question_id)

        if entity:
            serialized = json.dumps(asdict(entity), default=str)
            await self._redis.setex(cache_key, redis_settings.quiz_cache_ttl, serialized)

        return entity

    async def get_by_quiz_id(self, quiz_id: uuid.UUID) -> list[QuestionEntity]:
        """Retrieves all questions for a quiz, utilizing cache.

        Args:
            quiz_id: The UUID of the parent quiz.

        Returns:
            A list of QuestionEntity objects.
        """
        cache_key = f"questions:quiz:{quiz_id}"
        cached = await self._redis.get(cache_key)

        if cached:
            try:
                data = json.loads(cached)
                return [self._deserialize_question(q) for q in data]
            except Exception:
                pass

        entities = await self._repo.get_by_quiz_id(quiz_id)

        if entities:
            serialized = json.dumps([asdict(q) for q in entities], default=str)
            await self._redis.setex(cache_key, redis_settings.quiz_cache_ttl, serialized)

        return entities

    async def add(self, entity: QuestionEntity, quiz_id: uuid.UUID) -> None:
        """Persists a new question and invalidates the parent quiz cache.

        Args:
            entity: The QuestionEntity to persist.
            quiz_id: The parent quiz UUID.
        """
        await self._repo.add(entity, quiz_id)
        await self._redis.delete(f"questions:quiz:{quiz_id}")
        await self._redis.delete(f"quiz:entity:{quiz_id}")

    async def update(self, entity: QuestionEntity) -> bool:
        """Updates a question and heavily invalidates parent caches to ensure consistency.

        Args:
            entity: The fully updated QuestionEntity.

        Returns:
            True if updated, False if not found.
        """
        updated = await self._repo.update(entity)
        if updated:
            await self._redis.delete(f"question:entity:{entity.id}")
            await self._invalidate_all_quiz_structures()
        return updated

    async def delete(self, question_id: uuid.UUID) -> bool:
        """Deletes a question and heavily invalidates parent caches.

        Args:
            question_id: The UUID of the question to delete.

        Returns:
            True if deleted, False if not found.
        """
        deleted = await self._repo.delete(question_id)
        if deleted:
            await self._redis.delete(f"question:entity:{question_id}")
            await self._invalidate_all_quiz_structures()
        return deleted

    async def get_by_ids(self, ids: list[uuid.UUID]) -> list[QuestionEntity]:
        """Retrieves multiple questions by their unique identifiers.

        Args:
            ids: A list of question UUIDs.

        Returns:
            A list of mapped QuestionEntity objects.
        """
        return await self._repo.get_by_ids(ids)

    async def _invalidate_all_quiz_structures(self) -> None:
        """Clears all complex quiz and question collections to guarantee strict consistency."""
        async for key in self._redis.scan_iter("quiz:entity:*"):
            await self._redis.delete(key)
        async for key in self._redis.scan_iter("questions:quiz:*"):
            await self._redis.delete(key)

    def _deserialize_question(self, data: dict[str, Any]) -> QuestionEntity:
        """Reconstructs a QuestionEntity from a dictionary payload.

        Args:
            data: The deserialized JSON dictionary.

        Returns:
            A strictly typed QuestionEntity.
        """
        return QuestionEntity(
            id=uuid.UUID(data["id"]),
            type=QuestionType(data["type"]),
            order_index=data["order_index"],
            text=data["text"],
            payload=data["payload"],
        )