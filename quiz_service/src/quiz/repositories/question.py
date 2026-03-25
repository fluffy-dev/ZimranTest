from __future__ import annotations

import uuid

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.quiz.entities import QuestionEntity
from src.quiz.models.question import Question


class QuestionRepository:
    """Provides data access operations for Question entities.

    Enforces an Entity-in / Entity-out contract, isolating the application
    domain from SQLAlchemy ORM specifics.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initializes the repository with a database session.

        Args:
            session: The SQLAlchemy asynchronous session.
        """
        self._session = session

    @staticmethod
    def _to_entity(model: Question) -> QuestionEntity:
        """Maps a Question SQLAlchemy model to a QuestionEntity domain object.

        Args:
            model: The SQLAlchemy Question model.

        Returns:
            The mapped QuestionEntity.
        """
        return QuestionEntity(
            id=model.id,
            type=model.type,
            order_index=model.order_index,
            text=model.text,
            payload=model.payload,
        )

    @staticmethod
    def _to_model(entity: QuestionEntity, quiz_id: uuid.UUID) -> Question:
        """Maps a QuestionEntity domain object to a Question SQLAlchemy model.

        Args:
            entity: The QuestionEntity domain object.
            quiz_id: The foreign key ID of the parent quiz.

        Returns:
            The mapped Question model.
        """
        return Question(
            id=entity.id,
            quiz_id=quiz_id,
            type=entity.type,
            order_index=entity.order_index,
            text=entity.text,
            payload=entity.payload,
        )

    async def get_by_id(self, question_id: uuid.UUID) -> QuestionEntity | None:
        """Retrieves a question by its unique identifier.

        Args:
            question_id: The UUID of the question.

        Returns:
            The QuestionEntity if found, otherwise None.
        """
        result = await self._session.execute(
            select(Question).where(Question.id == question_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_quiz_id(self, quiz_id: uuid.UUID) -> list[QuestionEntity]:
        """Retrieves all questions associated with a specific quiz.

        Args:
            quiz_id: The UUID of the parent quiz.

        Returns:
            A list of associated QuestionEntity objects ordered by index.
        """
        result = await self._session.execute(
            select(Question)
            .where(Question.quiz_id == quiz_id)
            .order_by(Question.order_index.asc())
        )
        models = result.scalars().all()
        return [self._to_entity(model) for model in models]

    async def add(self, entity: QuestionEntity, quiz_id: uuid.UUID) -> None:
        """Persists a new question entity to the database.

        Args:
            entity: The QuestionEntity to persist.
            quiz_id: The parent quiz UUID.
        """
        model = self._to_model(entity, quiz_id)
        self._session.add(model)
        await self._session.flush()

    async def update(self, entity: QuestionEntity) -> bool:
        """Updates an existing question's mutable fields.

        Args:
            entity: The fully updated QuestionEntity.

        Returns:
            True if the record was successfully updated, False if not found.
        """
        stmt = (
            update(Question)
            .where(Question.id == entity.id)
            .values(
                text=entity.text,
                payload=entity.payload,
                order_index=entity.order_index,
                type=entity.type,
            )
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    async def delete(self, question_id: uuid.UUID) -> bool:
        """Removes a question from the database.

        Args:
            question_id: The UUID of the question to delete.

        Returns:
            True if the record was deleted, False if not found.
        """
        stmt = delete(Question).where(Question.id == question_id)
        result = await self._session.execute(stmt)
        return result.rowcount > 0