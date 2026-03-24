from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, MagicMock

from src.app import app
from src.uow import SqlAlchemyUnitOfWork


@pytest.fixture
async def client():
    """Provides a managed httpx AsyncClient for the FastAPI app."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac


@pytest.fixture
def mock_uow_e2e(mock_uow):
    """Overrides the real SqlAlchemyUnitOfWork with a mock for E2E tests.
    
    Uses the mock_uow fixture defined in the root conftest.py.
    """
    app.dependency_overrides[SqlAlchemyUnitOfWork] = lambda: mock_uow
    yield mock_uow
    app.dependency_overrides.clear()
