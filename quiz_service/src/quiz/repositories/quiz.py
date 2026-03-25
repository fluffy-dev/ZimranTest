from typing import Any
import uuid

from sqlalchemy import select, update, func
from sqlalchemy.orm import selectinload

from src.config.database.session import ISession
from src.quiz.models.quiz import Quiz, Question
from src.quiz.entities import QuizEntity, QuestionEntity
from shared.logging import get_logger

logger = get_logger(__name__)


def _map_question_entity(q: Question) -> QuestionEntity:
    """Helper to map a Question model to a QuestionEntity."""
    return QuestionEntity(
        id=q.id,
        type=q.type,
        order_index=q.order_index,
        text=q.text,
        payload=q.payload,
    )


def _map_quiz_entity(q: Quiz) -> QuizEntity:
    """Helper to map a Quiz model to a QuizEntity."""
    return QuizEntity(
        id=q.id,
        title=q.title,
        description=q.description,
        is_active=q.is_active,
        questions=[_map_question_entity(quest) for quest in q.questions],
    )


class QuizRepository:
    """Data access layer for quizzes and questions.
    
    Retrieves and maps database models to domain entities.
    """

    def __init__(self, session: ISession) -> None:
        """Initializes the repository with a database session.

        Args:
            session: SQLAlchemy async session.
        """
        self._session = session

    async def get_all_active(self, limit: int = 50, offset: int = 0) -> list[QuizEntity]:
        """Retrieves a paginated list of all active quizzes.

        Args:
            limit: Maximum number of quizzes to return.
            offset: Number of items to skip.

        Returns:
            list[QuizEntity]: List of active quiz entities.
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
        """Counts the total number of active quizzes.

        Returns:
            int: The total count.
        """
        result = await self._session.execute(
            select(func.count()).select_from(Quiz).where(Quiz.is_active.is_(True))
        )
        return result.scalar_one()

    async def get_by_id(self, quiz_id: uuid.UUID) -> QuizEntity | None:
        """Retrieves a specific quiz by its ID.

        Args:
            quiz_id: Unique identifier for the quiz.

        Returns:
            QuizEntity | None: The found entity or None.
        """
        result = await self._session.execute(
            select(Quiz)
            .where(Quiz.id == quiz_id)
            .options(selectinload(Quiz.questions))
        )
        quiz = result.scalar_one_or_none()
        return _map_quiz_entity(quiz) if quiz else None

    async def get_questions_by_ids(self, question_ids: list[uuid.UUID]) -> list[QuestionEntity]:
        """Retrieves multiple questions by their IDs.

        Args:
            question_ids: List of question IDs to fetch.

        Returns:
            list[QuestionEntity]: List of found question entities.
        """
        result = await self._session.execute(
            select(Question).where(Question.id.in_(question_ids))
        )
        return [_map_question_entity(q) for q in result.scalars().all()]

    async def create(self, title: dict[str, Any], description: dict[str, Any] | None = None) -> QuizEntity:
        """Creates a new quiz record.

        Args:
            title: Localized title dictionary.
            description: Optional localized description dictionary.

        Returns:
            QuizEntity: Domain representation of the created quiz.
        """
        quiz = Quiz(title=title, description=description)
        self._session.add(quiz)
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
        """Adds a new question to an existing quiz.

        Args:
            quiz_id: ID of the parent quiz.
            question_type: Type of question being added.
            text: Localized question text.
            payload: Question-specific configuration payload.
            order_index: Position index for sorting.

        Returns:
            QuestionEntity: Domain representation of the added question.
        """
        question = Question(
            quiz_id=quiz_id,
            type=question_type,
            text=text,
            payload=payload,
            order_index=order_index,
        )
        self._session.add(question)
        return _map_question_entity(question)

    async def set_active(self, quiz_id: uuid.UUID, *, is_active: bool) -> None:
        """Updates the activation status of a quiz.

        Args:
            quiz_id: Unique identifier for the quiz.
            is_active: Status to set.
        """
        result = await self._session.execute(select(Quiz).where(Quiz.id == quiz_id))
        quiz = result.scalar_one_or_none()
        if quiz:
            quiz.is_active = is_active
        else:
            logger.warning(f"Quiz {quiz_id} not found for activation update.")
