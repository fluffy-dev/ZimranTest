from __future__ import annotations

from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from src.attempt.models.user_question_answer import UserQuestionAnswer


class UserQuestionAnswerRepository:
    """Repository for managing UserQuestionAnswer entities."""

    def __init__(self, session: AsyncSession) -> None:
        """
        Initializes the repository with a database session.

        Args:
            session: The SQLAlchemy asynchronous session.
        """
        self._session = session

    async def bulk_create(self, answers: Sequence[UserQuestionAnswer]) -> None:
        """
        Persists multiple user question answers to the database.

        Args:
            answers: A sequence of UserQuestionAnswer model instances.
        """
        self._session.add_all(answers)