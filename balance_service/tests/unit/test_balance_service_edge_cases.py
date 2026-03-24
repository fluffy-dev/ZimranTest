from __future__ import annotations

import uuid
from types import SimpleNamespace
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from src.balance.service.balance import BalanceService
from shared.schemas import QuizRewardEvent, QuizRewardPayload


def make_balance(user_id: uuid.UUID, amount: int = 0) -> SimpleNamespace:
    """Creates a lightweight BalanceEntity-like object."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        amount=amount,
        updated_at=datetime.now(tz=timezone.utc),
    )


def make_transaction(user_id: uuid.UUID, amount: int, txn_type: str = "credit") -> SimpleNamespace:
    """Creates a lightweight BalanceTransactionEntity-like object."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        type=txn_type,
        amount=amount,
        description="Test transaction",
        idempotency_key=uuid.uuid4(),
        created_at=datetime.now(tz=timezone.utc),
    )


@pytest.fixture
def mock_repo():
    return AsyncMock()


@pytest.fixture
def mock_uow(mock_repo):
    uow = AsyncMock()
    uow.balances = mock_repo
    uow.commit = AsyncMock()
    uow.rollback = AsyncMock()
    uow.__aenter__.return_value = uow
    uow.__aexit__.return_value = None
    return uow


@pytest.fixture
def service(mock_uow):
    return BalanceService(uow=mock_uow)


class TestGetBalance:
    async def test_returns_existing_balance(self, service, mock_repo):
        """Returns balance if user already has one."""
        user_id = uuid.uuid4()
        mock_repo.get_by_user_id.return_value = make_balance(user_id, 500)

        result = await service.get_balance(user_id)

        assert result.amount == 500
        mock_repo.upsert_credit.assert_not_awaited()

    async def test_creates_initial_balance_when_none(self, service, mock_repo, mock_uow):
        """Creates a zero balance when user has no existing record."""
        user_id = uuid.uuid4()
        mock_repo.get_by_user_id.return_value = None
        mock_repo.upsert_credit.return_value = make_balance(user_id, 0)

        result = await service.get_balance(user_id)

        assert result.amount == 0
        mock_repo.upsert_credit.assert_awaited_once()
        call_kwargs = mock_repo.upsert_credit.call_args.kwargs
        assert call_kwargs["amount"] == 0
        assert call_kwargs["description"] == "Initial balance setup"
        mock_uow.commit.assert_awaited_once()


class TestCreditFromQuizEvent:
    async def test_negative_coins_skips(self, service, mock_repo):
        """Events with zero or negative coins skip the credit operation."""
        user_id = uuid.uuid4()
        event = QuizRewardEvent(
            payload=QuizRewardPayload(
                user_id=user_id,
                quiz_id=uuid.uuid4(),
                attempt_id=uuid.uuid4(),
                newly_rewarded_question_ids=[],
                coins_to_award=0,
            ),
        )
        mock_repo.get_by_user_id.return_value = make_balance(user_id, 100)

        result = await service.credit_from_quiz_event(event)

        assert result.amount == 100
        mock_repo.upsert_credit.assert_not_awaited()

    async def test_zero_coins_creates_balance_if_none(self, service, mock_repo, mock_uow):
        """Zero coins event creates initial balance if user has none."""
        user_id = uuid.uuid4()
        event = QuizRewardEvent(
            payload=QuizRewardPayload(
                user_id=user_id,
                quiz_id=uuid.uuid4(),
                attempt_id=uuid.uuid4(),
                newly_rewarded_question_ids=[],
                coins_to_award=0,
            ),
        )
        mock_repo.get_by_user_id.return_value = None
        mock_repo.upsert_credit.return_value = make_balance(user_id, 0)

        result = await service.credit_from_quiz_event(event)

        assert result.amount == 0
        mock_uow.commit.assert_awaited_once()


class TestGetTransactions:
    async def test_pagination_offset(self, service, mock_repo):
        """Page 2 with page_size 10 calculates offset=10."""
        user_id = uuid.uuid4()
        mock_repo.get_transactions.return_value = []

        await service.get_transactions(user_id, page=2, page_size=10)

        mock_repo.get_transactions.assert_awaited_once_with(
            user_id=user_id, limit=10, offset=10
        )

    async def test_returns_transaction_list(self, service, mock_repo):
        """Returns list of transactions from repository."""
        user_id = uuid.uuid4()
        txns = [make_transaction(user_id, 100), make_transaction(user_id, 200)]
        mock_repo.get_transactions.return_value = txns

        result = await service.get_transactions(user_id)

        assert len(result) == 2
        assert result[0].amount == 100
        assert result[1].amount == 200
