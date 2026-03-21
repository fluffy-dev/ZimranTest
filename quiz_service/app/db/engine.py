from __future__ import annotations

from asyncio import current_task
from collections.abc import AsyncGenerator

from sqlalchemy import exc
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_scoped_session,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


class DatabaseHelper:
    """Async SQLAlchemy engine and session factory wrapper."""

    def __init__(self, url: str, echo: bool = False) -> None:
        self.engine = create_async_engine(
            url=url,
            echo=echo,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_timeout=settings.DB_POOL_TIMEOUT,
            pool_pre_ping=True,
        )
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )

    def get_scoped_session(self) -> async_scoped_session[AsyncSession]:
        return async_scoped_session(
            session_factory=self.session_factory,
            scopefunc=current_task,
        )

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """FastAPI dependency that yields a transactional DB session per request."""
        session: AsyncSession = self.session_factory()
        try:
            yield session
        except exc.SQLAlchemyError:
            await session.rollback()
            raise
        finally:
            await session.close()


db_helper = DatabaseHelper(url=settings.DATABASE_URL, echo=settings.DEBUG)
