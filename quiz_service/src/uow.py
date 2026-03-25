from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config.database.engine import db_helper
from src.attempt.repositories.quiz_attempt import QuizAttemptRepository
from src.attempt.repositories.user_question_answer import UserQuestionAnswerRepository
from src.attempt.repositories.user_rewarded_question import UserRewardedQuestionRepository
from src.attempt.repositories.outbox_event import OutboxEventRepository
from src.quiz.repositories.quiz import QuizRepository


class AbstractUnitOfWork(ABC):
    """
    Defines the transactional boundary for quiz operations.
    Automatically handles rollback on exceptions.
    """

    quiz_attempts: QuizAttemptRepository
    user_answers: UserQuestionAnswerRepository
    user_rewards: UserRewardedQuestionRepository
    outbox: OutboxEventRepository
    quizzes: QuizRepository

    async def __aenter__(self) -> AbstractUnitOfWork:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            await self.rollback()

    @abstractmethod
    async def commit(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def rollback(self) -> None:
        raise NotImplementedError


class SqlAlchemyUnitOfWork(AbstractUnitOfWork):
    """
    SQLAlchemy-backed UoW.
    Creates a fresh session on entry and safely closes it on exit.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession] | None = None) -> None:
        self._session_factory = session_factory or db_helper.session_factory

    async def __aenter__(self) -> SqlAlchemyUnitOfWork:
        self._session: AsyncSession = self._session_factory()

        self.quiz_attempts = QuizAttemptRepository(self._session)
        self.user_answers = UserQuestionAnswerRepository(self._session)
        self.user_rewards = UserRewardedQuestionRepository(self._session)
        self.outbox = OutboxEventRepository(self._session)
        self.quizzes = QuizRepository(self._session)

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await super().__aexit__(exc_type, exc_val, exc_tb)
        await self._session.close()

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()


IUnitOfWork = Annotated[AbstractUnitOfWork, Depends(SqlAlchemyUnitOfWork)]