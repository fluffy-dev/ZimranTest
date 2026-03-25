from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.attempt.models.user_rewarded_question import UserRewardedQuestion
from src.attempt.entities import UserRewardedQuestionEntity


class UserRewardedQuestionRepository:
    """Repository for managing UserRewardedQuestion domain entities."""

    def __init__(self, session: AsyncSession) -> None:
        """
        Initializes the repository with a database session.

        Args:
            session: The SQLAlchemy asynchronous session.
        """
        self._session = session

    async def get_rewarded_ids_by_questions(
        self, user_id: uuid.UUID, question_ids: Sequence[uuid.UUID]
    ) -> set[uuid.UUID]:
        """
        Retrieves a subset of question IDs that the user has already been rewarded for.

        Args:
            user_id: The UUID of the user.
            question_ids: A sequence of question UUIDs to check against.

        Returns:
            A set of question UUIDs that have already been rewarded.
        """
        if not question_ids:
            return set()

        result = await self._session.execute(
            select(UserRewardedQuestion.question_id)
            .where(
                UserRewardedQuestion.user_id == user_id,
                UserRewardedQuestion.question_id.in_(question_ids),
            )
        )
        return {row[0] for row in result.all()}

    async def bulk_add(self, entities: Sequence[UserRewardedQuestionEntity]) -> None:
        """
        Translates a sequence of domain entities into ORM models and stages them for insertion.

        Args:
            entities: A sequence of UserRewardedQuestionEntity objects.
        """
        models = [
            UserRewardedQuestion(
                user_id=entity.user_id,
                question_id=entity.question_id,
                quiz_id=entity.quiz_id,
                rewarded_at=entity.rewarded_at,
            )
            for entity in entities
        ]
        self._session.add_all(models)