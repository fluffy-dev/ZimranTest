from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from src.attempt.repositories.attempt import AttemptRepository
from src.attempt.repositories.outbox import OutboxRepository
from src.quiz.repositories.quiz import QuizRepository


class AbstractUnitOfWork(ABC):
    """Abstract base class for the Unit of Work pattern.
    
    Provides an interface for managing transactional boundaries and repository access.
    """

    attempts: AttemptRepository
    outbox: OutboxRepository
    quizzes: QuizRepository

    async def __aenter__(self) -> AbstractUnitOfWork:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.rollback()

    @abstractmethod
    async def commit(self) -> None:
        """Commits the current transaction."""
        raise NotImplementedError

    @abstractmethod
    async def rollback(self) -> None:
        """Rolls back the current transaction."""
        raise NotImplementedError


class SqlAlchemyUnitOfWork(AbstractUnitOfWork):
    """SQLAlchemy implementation of the Unit of Work pattern.
    
    Manages the lifecycle of an AsyncSession and orchestrates repositories.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initializes the UoW with a session and its repositories.

        Args:
            session: SQLAlchemy async session.
        """
        self._session = session
        self.attempts = AttemptRepository(session)
        self.outbox = OutboxRepository(session)
        self.quizzes = QuizRepository(session)

    async def commit(self) -> None:
        """Commits the database session."""
        await self._session.commit()

    async def rollback(self) -> None:
        """Rolls back the database session."""
        await self._session.rollback()


from typing import Annotated
from fastapi import Depends

IUnitOfWork: type[SqlAlchemyUnitOfWork] = Annotated[
    SqlAlchemyUnitOfWork, Depends()
]
