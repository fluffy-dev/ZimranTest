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
    Retrieves and maps database models to localized domain entities.
    """

    def __init__(self, session: ISession) -> None:
        """Initializes the repository with a database session."""
        self._session = session

    async def get_all_active(self, limit: int = 50, offset: int = 0) -> list[QuizEntity]:
        """
        Retrieves a paginated list of all active quizzes.

        Args:
            limit: Maximum number of quizzes to return.
            offset: Number of quizzes to skip for pagination.

        Returns:
            list[QuizEntity]: List of active quiz domain entities.
        """
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
        """
        Counts the total number of active quizzes in the system.

        Returns:
            int: The count of active quizzes.
        """
        result = await self._session.execute(
            select(func.count()).select_from(Quiz).where(Quiz.is_active.is_(True))
        )
        return result.scalar_one()

    async def get_by_id(self, quiz_id: uuid.UUID) -> QuizEntity | None:
        """
        Retrieves a specific quiz by its ID, eagerly loading its questions.

        Args:
            quiz_id: The unique identifier of the quiz.

        Returns:
            QuizEntity | None: The found quiz domain entity or None.
        """
        result = await self._session.execute(
            select(Quiz)
            .where(Quiz.id == quiz_id)
            .options(selectinload(Quiz.questions))
        )
        quiz = result.scalar_one_or_none()
        return _map_quiz_entity(quiz) if quiz else None

    async def get_questions_by_ids(self, question_ids: list[uuid.UUID]) -> list[QuestionEntity]:
        """
        Retrieves multiple questions by their unique identifiers.

        Args:
            question_ids: List of question IDs to fetch.

        Returns:
            list[QuestionEntity]: List of found question domain entities.
        """
        result = await self._session.execute(
            select(Question).where(Question.id.in_(question_ids))
        )
        return [_map_question_entity(q) for q in result.scalars().all()]

    async def create(self, title: dict[str, Any], description: dict[str, Any] | None = None) -> QuizEntity:
        """
        Creates a new quiz record in the database.

        Args:
            title: Localization dictionary for the quiz title.
            description: Optional localization dictionary for the description.

        Returns:
            QuizEntity: The newly created quiz domain entity.
        """
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
        """
        Creates and adds a new question to a specific quiz.

        Args:
            quiz_id: ID of the quiz to which the question belongs.
            question_type: The type of the question (e.g., 'single_choice').
            text: Localization dictionary for the question text.
            payload: Type-specific logic/content payload.
            order_index: Position of the question within the quiz.

        Returns:
            QuestionEntity: The newly created question domain entity.
        """
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
        """
        Updates the active status of a quiz.

        Args:
            quiz_id: The unique identifier of the quiz.
            is_active: The boolean status to set.
        """
        await self._session.execute(
            update(Quiz).where(Quiz.id == quiz_id).values(is_active=is_active)
        )
