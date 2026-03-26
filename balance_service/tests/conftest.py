"""
Shared test fixtures for the balance_service test suite.

Provides:
  - Factory helpers (make_balance, make_transaction, make_quiz_reward_event)
  - AsyncMock-based repository and UoW fixtures
  - FastAPI TestClient factory with lifespan mocking
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from shared.schemas import QuizRewardEvent, QuizRewardPayload
from src.balance.entities import BalanceEntity, BalanceTransactionEntity
from src.balance.enum import TransactionType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def make_uuid() -> uuid.UUID:
    return uuid.uuid4()


def make_balance(
    *,
    balance_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    amount: int = 500,
) -> BalanceEntity:
    return BalanceEntity(
        id=balance_id or make_uuid(),
        user_id=user_id or make_uuid(),
        amount=amount,
        updated_at=utcnow(),
    )


def make_transaction(
    *,
    tx_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    amount: int = 100,
    idempotency_key: uuid.UUID | None = None,
    tx_type: TransactionType = TransactionType.CREDIT,
    description: str | None = "Quiz reward: attempt test",
) -> BalanceTransactionEntity:
    return BalanceTransactionEntity(
        id=tx_id or make_uuid(),
        user_id=user_id or make_uuid(),
        type=tx_type,
        amount=amount,
        description=description,
        idempotency_key=idempotency_key or make_uuid(),
        created_at=utcnow(),
    )


def make_quiz_reward_event(
    *,
    event_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    quiz_id: uuid.UUID | None = None,
    attempt_id: uuid.UUID | None = None,
    coins: int = 100,
    question_ids: list[uuid.UUID] | None = None,
) -> QuizRewardEvent:
    return QuizRewardEvent(
        event_id=event_id or make_uuid(),
        payload=QuizRewardPayload(
            user_id=user_id or make_uuid(),
            quiz_id=quiz_id or make_uuid(),
            attempt_id=attempt_id or make_uuid(),
            newly_rewarded_question_ids=question_ids or [make_uuid()],
            coins_to_award=coins,
        ),
    )


# ---------------------------------------------------------------------------
# Repository mocks
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_balance_repo():
    repo = AsyncMock()
    repo.get_by_user_id = AsyncMock(return_value=None)
    repo.upsert_amount = AsyncMock(return_value=make_balance())
    return repo


@pytest.fixture
def mock_transaction_repo():
    repo = AsyncMock()
    repo.get_by_idempotency_key = AsyncMock(return_value=None)
    repo.insert_idempotent = AsyncMock(return_value=None)
    repo.get_paginated_by_user = AsyncMock(return_value=[])
    repo.count_by_user = AsyncMock(return_value=0)
    return repo


@pytest.fixture
def mock_uow(mock_balance_repo, mock_transaction_repo):
    uow = AsyncMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)
    uow.commit = AsyncMock()
    uow.rollback = AsyncMock()
    uow.balances = mock_balance_repo
    uow.transactions = mock_transaction_repo
    return uow


# ---------------------------------------------------------------------------
# FastAPI TestClient factory with lifespan suppressed
# ---------------------------------------------------------------------------

@pytest.fixture
def app_client():
    """
    Returns a FastAPI TestClient with the RabbitMQ lifespan mocked out.
    Without this, the TestClient would attempt to connect to a real broker.
    """
    async def _mock_supervise():
        try:
            await asyncio.sleep(float("inf"))
        except asyncio.CancelledError:
            pass

    with patch("src.lifespan._supervise_consumer", side_effect=_mock_supervise):
        with patch("src.lifespan.start_consumer", new_callable=AsyncMock) as mock_start:
            mock_consumer = AsyncMock()
            mock_consumer.is_connected = True
            mock_consumer.consume = AsyncMock()
            mock_consumer.close = AsyncMock()
            mock_start.return_value = mock_consumer

            from src.app import app
            with TestClient(app, raise_server_exceptions=False) as client:
                yield client


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    """Ensure dependency overrides are cleaned up after every test."""
    from src.app import app
    yield
    app.dependency_overrides.clear()