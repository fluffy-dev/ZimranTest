from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Annotated, AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.balance.repositories.balance import BalanceRepository
from src.balance.repositories.balance_transaction import BalanceTransactionRepository
from src.config.database.engine import db_helper


class AbstractUnitOfWork(ABC):
    """Defines the transactional boundary for all balance domain operations.

    Attributes:
        balances: Repository for managing aggregate user balance states.
        transactions: Repository for managing the immutable balance ledger.
    """

    balances: BalanceRepository
    transactions: BalanceTransactionRepository

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
    and safely closes connections upon exit.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Initializes the Unit of Work with the session factory.

        Args:
            session_factory: The SQLAlchemy asynchronous session maker.
        """
        self._session_factory = session_factory

    async def __aenter__(self) -> SqlAlchemyUnitOfWork:
        """Enters the context manager, instantiating the session and repositories.

        Returns:
            The populated SqlAlchemyUnitOfWork instance.
        """
        self._session: AsyncSession = self._session_factory()

        self.balances = BalanceRepository(self._session)
        self.transactions = BalanceTransactionRepository(self._session)

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


async def get_uow() -> AsyncGenerator[AbstractUnitOfWork, None]:
    """Dependency injection factory for the Unit of Work.

    Yields:
        An isolated instance of the SqlAlchemyUnitOfWork.
    """
    uow = SqlAlchemyUnitOfWork(session_factory=db_helper.session_factory)
    yield uow


IUnitOfWork: type[AbstractUnitOfWork] = Annotated[AbstractUnitOfWork, Depends(get_uow)]