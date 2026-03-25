from __future__ import annotations

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.quiz.entities import QuestionEntity, QuizEntity
from src.quiz.models.question import Question
from src.quiz.models.quiz import Quiz


class QuizRepository:
    """
    Provides data access operations for Quiz entities.

    Enforces an Entity-in / Entity-out contract and optimizes read/write
    operations for the core Quiz domain.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initializes the repository with a database session.

        Args:
            session: The SQLAlchemy asynchronous session.
        """
        self._session = session

    @staticmethod
    def _to_entity(model: Quiz) -> QuizEntity:
        """Maps a fully loaded Quiz SQLAlchemy model to a QuizEntity.

        Args:
            model: The SQLAlchemy Quiz model with eagerly loaded questions.

        Returns:
            The mapped QuizEntity containing nested questions.
        """
        questions = [
            QuestionEntity(
                id=q.id,
                type=q.type,
                order_index=q.order_index,
                text=q.text,
                payload=q.payload,
            )
            for q in getattr(model, "questions", [])
        ]

        return QuizEntity(
            id=model.id,
            title=model.title,
            description=model.description,
            is_active=model.is_active,
            question_count=len(questions),
            questions=questions,
        )

    @staticmethod
    def _to_summary_entity(model: Quiz, question_count: int) -> QuizEntity:
        """Maps a lightweight Quiz SQLAlchemy model to a QuizEntity.

        Args:
            model: The SQLAlchemy Quiz model without nested questions.
            question_count: The pre-calculated integer count of questions.

        Returns:
            The mapped QuizEntity configured for summary list views.
        """
        return QuizEntity(
            id=model.id,
            title=model.title,
            description=model.description,
            is_active=model.is_active,
            question_count=question_count,
            questions=[],
        )

    @staticmethod
    def _to_model(entity: QuizEntity) -> Quiz:
        """Maps a QuizEntity domain object to a Quiz SQLAlchemy model.

        Args:
            entity: The QuizEntity domain object.

        Returns:
            The mapped Quiz model.
        """
        return Quiz(
            id=entity.id,
            title=entity.title,
            description=entity.description,
            is_active=entity.is_active,
        )

    async def get_by_id(self, quiz_id: uuid.UUID) -> QuizEntity | None:
        """Retrieves a fully hydrated quiz by its unique identifier.

        Args:
            quiz_id: The UUID of the quiz.

        Returns:
            The QuizEntity if found, otherwise None.
        """
        result = await self._session.execute(
            select(Quiz)
            .where(Quiz.id == quiz_id)
            .options(selectinload(Quiz.questions))
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_all_active(self, limit: int, offset: int) -> list[QuizEntity]:
        """Retrieves a paginated list of active quizzes with computed question counts.

        Args:
            limit: The maximum number of records to return.
            offset: The number of records to skip.

        Returns:
            A list of mapped active QuizEntity objects optimized for summary display.
        """
        count_stmt = (
            select(func.count(Question.id))
            .where(Question.quiz_id == Quiz.id)
            .correlate(Quiz)
            .scalar_subquery()
        )

        stmt = (
            select(Quiz, count_stmt.label("question_count"))
            .where(Quiz.is_active.is_(True))
            .order_by(Quiz.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self._session.execute(stmt)
        rows = result.all()
        return [self._to_summary_entity(row.Quiz, row.question_count) for row in rows]

    async def count_active(self) -> int:
        """Aggregates the total count of active quizzes.

        Returns:
            The integer count of active quizzes.
        """
        result = await self._session.execute(
            select(func.count()).select_from(Quiz).where(Quiz.is_active.is_(True))
        )
        return result.scalar_one()

    async def add(self, entity: QuizEntity) -> None:
        """Persists a new quiz entity to the database.

        Args:
            entity: The QuizEntity to persist.
        """
        model = self._to_model(entity)
        self._session.add(model)
        await self._session.flush()

    async def set_active_status(self, quiz_id: uuid.UUID, is_active: bool) -> bool:
        """Atomically updates the active status of a quiz without hydrating the model.

        Args:
            quiz_id: The UUID of the quiz to update.
            is_active: The boolean status to apply.

        Returns:
            True if the record was successfully updated, False if not found.
        """
        stmt = (
            update(Quiz)
            .where(Quiz.id == quiz_id)
            .values(is_active=is_active)
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    async def update(self, entity: QuizEntity) -> bool:
        """Updates an existing quiz's text attributes.

        Args:
            entity: The fully updated QuizEntity.

        Returns:
            True if updated, False if not found.
        """
        stmt = (
            update(Quiz)
            .where(Quiz.id == entity.id)
            .values(title=entity.title, description=entity.description)
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0