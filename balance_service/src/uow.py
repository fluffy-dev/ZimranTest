from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.database.engine import db_helper
from src.balance.repositories.balance import BalanceRepository


class AbstractUnitOfWork(ABC):
    """Defines the transactional boundary for a business operation.

    Repositories are accessed as attributes. The caller is responsible
    for calling ``commit()`` on success; ``rollback()`` is triggered
    automatically when the context manager exits with an exception.
    """

    balances: BalanceRepository

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
    """SQLAlchemy-backed Unit of Work.

    Creates a fresh ``AsyncSession`` on entry, initialises the balance
    repository with that session, and manages commit / rollback.
    """

    def __init__(self) -> None:
        self._session_factory = db_helper.session_factory

    async def __aenter__(self) -> SqlAlchemyUnitOfWork:
        self._session: AsyncSession = self._session_factory()
        self.balances = BalanceRepository(self._session)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await super().__aexit__(exc_type, exc_val, exc_tb)
        await self._session.close()

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()


IUnitOfWor: type[SqlAlchemyUnitOfWork] = Annotated[SqlAlchemyUnitOfWork, Depends()]
