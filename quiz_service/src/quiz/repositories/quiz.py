from typing import Any
import uuid

from sqlalchemy import select, update, func
from sqlalchemy.orm import selectinload

from src.config.database.session import ISession
from src.quiz.models.quiz import Quiz, Question
from src.quiz.entities import QuizEntity, QuestionEntity


def _map_question_entity(q: Question) -> QuestionEntity:
    return QuestionEntity(
        id=q.id,
        type=q.type,
        order_index=q.order_index,
        text=q.text,
        payload=q.payload,
    )


def _map_quiz_entity(q: Quiz) -> QuizEntity:
    return QuizEntity(
        id=q.id,
        title=q.title,
        description=q.description,
        is_active=q.is_active,
        questions=[_map_question_entity(quest) for quest in q.questions],
    )


class QuizRepository:
    """
    Data access layer for quizzes and questions.
    Returns domain entities to decouple the database logic from business logic.
    """

    def __init__(self, session: ISession) -> None:
        self._session = session

    async def get_all_active(self, limit: int = 50, offset: int = 0) -> list[QuizEntity]:
        result = await self._session.execute(
            select(Quiz)
            .where(Quiz.is_active.is_(True))
            .options(selectinload(Quiz.questions))
            .offset(offset)
            .limit(limit)
            .order_by(Quiz.created_at.desc())
        )
        return [_map_quiz_entity(q) for q in result.scalars().all()]

    async def count_active(self) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(Quiz).where(Quiz.is_active.is_(True))
        )
        return result.scalar_one()

    async def get_by_id(self, quiz_id: uuid.UUID) -> QuizEntity | None:
        result = await self._session.execute(
            select(Quiz)
            .where(Quiz.id == quiz_id)
            .options(selectinload(Quiz.questions))
        )
        quiz = result.scalar_one_or_none()
        return _map_quiz_entity(quiz) if quiz else None

    async def get_questions_by_ids(self, question_ids: list[uuid.UUID]) -> list[QuestionEntity]:
        result = await self._session.execute(
            select(Question).where(Question.id.in_(question_ids))
        )
        return [_map_question_entity(q) for q in result.scalars().all()]

    async def create(self, title: dict[str, Any], description: dict[str, Any] | None = None) -> QuizEntity:
        quiz = Quiz(title=title, description=description)
        self._session.add(quiz)
        await self._session.flush()
        await self._session.refresh(quiz)
        
        # We need to manually initialize the empty Relationship to map it correctly
        quiz.questions = [] 
        return _map_quiz_entity(quiz)

    async def add_question(
        self,
        quiz_id: uuid.UUID,
        question_type: str,
        text: dict[str, Any],
        payload: dict[str, Any],
        order_index: int,
    ) -> QuestionEntity:
        question = Question(
            quiz_id=quiz_id,
            type=question_type,
            text=text,
            payload=payload,
            order_index=order_index,
        )
        self._session.add(question)
        await self._session.flush()
        return _map_question_entity(question)

    async def set_active(self, quiz_id: uuid.UUID, *, is_active: bool) -> None:
        await self._session.execute(
            update(Quiz).where(Quiz.id == quiz_id).values(is_active=is_active)
        )
