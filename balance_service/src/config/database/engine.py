from asyncio import current_task
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
    async_scoped_session,
)

from src.config.database.settings import settings as db_settings

class DatabaseHelper:
    """Class helper for work with database session"""

    def __init__(self, url: str, echo: bool = False, pool_size: int = 5, max_overflow: int = 10):
        self.engine = create_async_engine(
            url=url, 
            echo=echo,
            pool_size=pool_size,
            max_overflow=max_overflow
        )

        self.session_factory = async_sessionmaker(
            bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False
        )

    def get_scope_session(self):
        return async_scoped_session(
            session_factory=self.session_factory, scopefunc=current_task
        )

    @asynccontextmanager
    async def get_db_session(self):
        from sqlalchemy import exc

        session: AsyncSession = self.session_factory()
        try:
            yield session
        except exc.SQLAlchemyError:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def get_session(self):
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
    url=db_settings.database_url,
    echo=db_settings.db_echo_log,
)
