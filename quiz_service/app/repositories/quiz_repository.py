from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.db.models import Question, Quiz
from app.dependencies.common import ISession
from shared.logging import get_logger

logger = get_logger(__name__)


class QuizRepository:
    """Data access layer for quizzes and questions."""

    def __init__(self, session: ISession) -> None:
        self._session = session

    async def get_all_active(
        self, limit: int = 50, offset: int = 0
    ) -> list[Quiz]:
        result = await self._session.execute(
            select(Quiz)
            .where(Quiz.is_active.is_(True))
            .options(selectinload(Quiz.questions))
            .offset(offset)
            .limit(limit)
            .order_by(Quiz.created_at.desc())
        )
        return list(result.scalars().all())

    async def count_active(self) -> int:
        from sqlalchemy import func

        result = await self._session.execute(
            select(func.count()).select_from(Quiz).where(Quiz.is_active.is_(True))
        )
        return result.scalar_one()

    async def get_by_id(self, quiz_id: uuid.UUID) -> Quiz | None:
        result = await self._session.execute(
            select(Quiz)
            .where(Quiz.id == quiz_id)
            .options(selectinload(Quiz.questions))
        )
        return result.scalar_one_or_none()

    async def get_questions_by_ids(
        self, question_ids: list[uuid.UUID]
    ) -> list[Question]:
        result = await self._session.execute(
            select(Question).where(Question.id.in_(question_ids))
        )
        return list(result.scalars().all())

    async def create(
        self,
        title: dict[str, Any],
        description: dict[str, Any] | None = None,
    ) -> Quiz:
        quiz = Quiz(title=title, description=description)
        self._session.add(quiz)
        await self._session.flush()
        await self._session.refresh(quiz)
        return quiz

    async def add_question(
        self,
        quiz_id: uuid.UUID,
        question_type: str,
        text: dict[str, Any],
        payload: dict[str, Any],
        order_index: int,
    ) -> Question:
        question = Question(
            quiz_id=quiz_id,
            type=question_type,
            text=text,
            payload=payload,
            order_index=order_index,
        )
        self._session.add(question)
        await self._session.flush()
        return question

    async def set_active(self, quiz_id: uuid.UUID, *, is_active: bool) -> None:
        await self._session.execute(
            update(Quiz).where(Quiz.id == quiz_id).values(is_active=is_active)
        )
