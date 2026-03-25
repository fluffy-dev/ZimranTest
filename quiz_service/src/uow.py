from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Annotated, AsyncGenerator

import redis.asyncio as aioredis
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.attempt.repositories.outbox_event import OutboxEventRepository
from src.attempt.repositories.quiz_attempt import QuizAttemptRepository
from src.attempt.repositories.user_question_answer import UserQuestionAnswerRepository
from src.attempt.repositories.user_rewarded_question import UserRewardedQuestionRepository
from src.config.database.engine import db_helper
from src.dependencies.common import IRedis

from src.quiz.repositories.cached_quiz import CachingQuizRepository
from src.quiz.repositories.cached_question import CachingQuestionRepository

from src.quiz.repositories.question import QuestionRepository
from src.quiz.repositories.quiz import QuizRepository


class AbstractUnitOfWork(ABC):
    """Defines the transactional and caching boundary for all domain operations.

    Attributes:
        quiz_attempts: Repository for managing quiz attempt states.
        user_answers: Repository for persisting user submitted answers.
        user_rewards: Repository for tracking distributed rewards.
        outbox: Repository for staging transactional outbox events.
        quizzes: Cache-enabled repository for quiz content metadata.
        questions: Cache-enabled repository for localized question content.
    """

    quiz_attempts: QuizAttemptRepository
    user_answers: UserQuestionAnswerRepository
    user_rewards: UserRewardedQuestionRepository
    outbox: OutboxEventRepository
    quizzes: CachingQuizRepository
    questions: CachingQuestionRepository

    async def __aenter__(self) -> AbstractUnitOfWork:
        """Enters the asynchronous context manager.

        Returns:
            The initialized Unit of Work instance.
        """
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exits the asynchronous context manager, rolling back on unhandled exceptions.

        Args:
            exc_type: The exception type if an error occurred.
            exc_val: The exception instance if an error occurred.
            exc_tb: The traceback if an error occurred.
        """
        if exc_type is not None:
            await self.rollback()

    @abstractmethod
    async def commit(self) -> None:
        """Commits the current transaction boundary to the persistent store."""
        raise NotImplementedError

    @abstractmethod
    async def rollback(self) -> None:
        """Rolls back the current transaction boundary, discarding uncommitted changes."""
        raise NotImplementedError


class SqlAlchemyUnitOfWork(AbstractUnitOfWork):
    """SQLAlchemy-backed implementation of the Unit of Work pattern.

    Creates a fresh database session on entry, resolves base repositories,
    wraps read-heavy repositories in Redis caching decorators, and safely closes
    connections upon exit.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        redis_client: aioredis.Redis,
    ) -> None:
        """Initializes the Unit of Work with connection factories.

        Args:
            session_factory: The SQLAlchemy asynchronous session maker.
            redis_client: The asynchronous Redis client instance.
        """
        self._session_factory = session_factory
        self._redis_client = redis_client

    async def __aenter__(self) -> SqlAlchemyUnitOfWork:
        """Enters the context manager, instantiating the session and all repositories.

        Returns:
            The populated SqlAlchemyUnitOfWork instance.
        """
        self._session: AsyncSession = self._session_factory()

        self.quiz_attempts = QuizAttemptRepository(self._session)
        self.user_answers = UserQuestionAnswerRepository(self._session)
        self.user_rewards = UserRewardedQuestionRepository(self._session)
        self.outbox = OutboxEventRepository(self._session)

        base_quiz_repo = QuizRepository(self._session)
        base_question_repo = QuestionRepository(self._session)

        self.quizzes = CachingQuizRepository(base_quiz_repo, self._redis_client)
        self.questions = CachingQuestionRepository(base_question_repo, self._redis_client)

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Safely tears down the session context, enforcing rollback on errors.

        Args:
            exc_type: The exception type if an error occurred.
            exc_val: The exception instance if an error occurred.
            exc_tb: The traceback if an error occurred.
        """
        if exc_type is not None:
            await self.rollback()
        await self._session.close()

    async def commit(self) -> None:
        """Commits pending SQLAlchemy session changes to the database."""
        await self._session.commit()

    async def rollback(self) -> None:
        """Reverts all pending SQLAlchemy session changes."""
        await self._session.rollback()


async def get_uow(redis: IRedis) -> AsyncGenerator[AbstractUnitOfWork, None]:
    """Dependency injection factory for the Unit of Work.

    Args:
        redis: The injected Redis client dependency.

    Yields:
        An isolated instance of the SqlAlchemyUnitOfWork.
    """
    uow = SqlAlchemyUnitOfWork(
        session_factory=db_helper.session_factory,
        redis_client=redis,
    )
    yield uow


IUnitOfWork: type[AbstractUnitOfWork] = Annotated[AbstractUnitOfWork, Depends(get_uow)]