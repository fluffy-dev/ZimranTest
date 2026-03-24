from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from types import SimpleNamespace

os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "test_db")
os.environ.setdefault("DB_USER", "test_user")
os.environ.setdefault("DB_PASSWORD", "test_password")

import pytest

from src.balance.service.balance import BalanceService
from shared.schemas import QuizRewardEvent, QuizRewardPayload


@pytest.fixture
def mock_uow():
    uow = AsyncMock()
    uow.balances = AsyncMock()
    uow.__aenter__.return_value = uow
    return uow


@pytest.fixture
def service(mock_uow):
    return BalanceService(uow=mock_uow)


@pytest.fixture
def make_event():
    def _make(user_id: uuid.UUID | None = None, coins: int = 100, event_id: uuid.UUID | None = None) -> QuizRewardEvent:
        return QuizRewardEvent(
            event_id=event_id or uuid.uuid4(),
            payload=QuizRewardPayload(
                user_id=user_id or uuid.uuid4(),
                quiz_id=uuid.uuid4(),
                attempt_id=uuid.uuid4(),
                newly_rewarded_question_ids=[uuid.uuid4()],
                coins_to_award=coins,
            )
        )
    return _make


@pytest.fixture
def make_balance_entity():
    def _make(user_id: uuid.UUID, amount: int = 0) -> SimpleNamespace:
        return SimpleNamespace(
            id=uuid.uuid4(),
            user_id=user_id,
            amount=amount,
            updated_at=datetime.now(tz=timezone.utc),
        )
    return _make


@pytest.fixture
def make_transaction_entity():
    def _make(user_id: uuid.UUID, amount: int, txn_type: str = "credit") -> SimpleNamespace:
        return SimpleNamespace(
            id=uuid.uuid4(),
            user_id=user_id,
            type=txn_type,
            amount=amount,
            description="Test transaction",
            idempotency_key=uuid.uuid4(),
            created_at=datetime.now(tz=timezone.utc),
        )
    return _make
