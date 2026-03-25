import asyncio
from typing import AsyncGenerator
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from src.app import app
from src.config.database.engine import db_helper
from src.libs.base_model import Base

# Use a test database URL (ensure this DB exists locally or in CI)
TEST_DB_URL = "postgresql+asyncpg://test_user:test_password@localhost:5432/test_db"

engine = create_async_engine(TEST_DB_URL, pool_size=5, echo=False)
TestingSessionLocal = async_sessionmaker(bind=engine, autoflush=False, autocommit=False)

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database():
    """Recreate tables before the test session starts."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provides a clean database session per test."""
    async with TestingSessionLocal() as session:
        yield session
        await session.rollback() # Ensure rollback after test

@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Overrides the FastAPI DB dependency and provides an async HTTP client."""
    async def override_get_session():
        yield db_session

    app.dependency_overrides[db_helper.get_session] = override_get_session
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
        
    app.dependency_overrides.clear()

@pytest.fixture
def auth_headers() -> dict:
    return {"X-User-ID": "11111111-1111-1111-1111-111111111111"}