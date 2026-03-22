from __future__ import annotations

from asyncio import current_task
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_scoped_session,
    async_sessionmaker,
    create_async_engine,
)

from src.config.database.settings import settings as db_settings


class DatabaseHelper:
    """Manages async SQLAlchemy engine and session lifecycle."""

    def __init__(
        self,
        url: str,
        echo: bool = False,
        pool_size: int = 5,
        max_overflow: int = 10,
    ) -> None:
        self.engine: AsyncEngine = create_async_engine(
            url=url,
            echo=echo,
            pool_size=pool_size,
            max_overflow=max_overflow,
        )

        self.session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )

    def get_scope_session(self) -> async_scoped_session[AsyncSession]:
        """Returns a scoped session bound to the current asyncio task."""
        return async_scoped_session(
            session_factory=self.session_factory,
            scopefunc=current_task,
        )

    @asynccontextmanager
    async def get_db_session(self) -> AsyncIterator[AsyncSession]:
        """Context manager yielding a session with automatic rollback on error."""
        from sqlalchemy import exc

        session: AsyncSession = self.session_factory()
        try:
            yield session
        except exc.SQLAlchemyError:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def get_session(self) -> AsyncIterator[AsyncSession]:
        """FastAPI dependency yielding a session with automatic rollback on error."""
        from sqlalchemy import exc

        session: AsyncSession = self.session_factory()
        try:
            yield session
        except exc.SQLAlchemyError:
            await session.rollback()
            raise
        finally:
            await session.close()


db_helper = DatabaseHelper(
    url=str(db_settings.database_url),
    echo=db_settings.db_echo_log,
    pool_size=db_settings.db_pool_size,
    max_overflow=db_settings.db_max_overflow,
)
