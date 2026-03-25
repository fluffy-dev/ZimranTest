from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func

from src.attempt.models.user_question_answer import UserQuestionAnswer
from src.attempt.entities import UserQuestionAnswerEntity


class UserQuestionAnswerRepository:
    """Repository for managing UserQuestionAnswer domain entities."""

    def __init__(self, session: AsyncSession) -> None:
        """
        Initializes the repository with a database session.

        Args:
            session: The SQLAlchemy asynchronous session.
        """
        self._session = session

    async def bulk_add(self, entities: Sequence[UserQuestionAnswerEntity]) -> None:
        """
        Translates a sequence of domain entities into ORM models and stages them for insertion.

        Args:
            entities: A sequence of UserQuestionAnswerEntity objects.
        """
        models = [
            UserQuestionAnswer(
                id=entity.id,
                attempt_id=entity.attempt_id,
                question_id=entity.question_id,
                answer_payload=entity.answer_payload,
                is_correct=entity.is_correct,
                answered_at=entity.answered_at,
            )
            for entity in entities
        ]
        self._session.add_all(models)

    async def upsert_draft(self, entity: UserQuestionAnswerEntity) -> None:
        """
        Upserts a user's draft answer, overwriting payload and timestamp on conflict.

        Args:
            entity: The UserQuestionAnswerEntity to upsert.
        """
        stmt = insert(UserQuestionAnswer).values(
            id=entity.id,
            attempt_id=entity.attempt_id,
            question_id=entity.question_id,
            answer_payload=entity.answer_payload,
            is_correct=entity.is_correct,
            answered_at=entity.answered_at,
        )

        stmt = stmt.on_conflict_do_update(
            index_elements=["attempt_id", "question_id"],
            set_={
                "answer_payload": stmt.excluded.answer_payload,
                "answered_at": func.now(),
            },
        )

        await self._session.execute(stmt)