from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.balance_service import BalanceService
from types import SimpleNamespace
from shared.schemas import QuizRewardEvent, QuizRewardPayload


def make_event(coins: int = 200) -> QuizRewardEvent:
    return QuizRewardEvent(
        payload=QuizRewardPayload(
            user_id=uuid.uuid4(),
            quiz_id=uuid.uuid4(),
            attempt_id=uuid.uuid4(),
            newly_rewarded_question_ids=[uuid.uuid4(), uuid.uuid4()],
            coins_to_award=coins,
        )
    )


def make_balance(user_id: uuid.UUID, amount: int = 0) -> SimpleNamespace:
    from datetime import datetime, timezone
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        amount=amount,
        updated_at=datetime.now(tz=timezone.utc),
    )


@pytest.fixture
def mock_repo():
    repo = AsyncMock()
    return repo


@pytest.fixture
def service(mock_repo):
    return BalanceService(repo=mock_repo)


class TestCreditFromQuizEvent:
    async def test_credits_correct_amount(self, service, mock_repo):
        event = make_event(coins=200)
        expected_balance = make_balance(event.payload.user_id, amount=200)
        mock_repo.upsert_credit.return_value = expected_balance

        result = await service.credit_from_quiz_event(event)

        mock_repo.upsert_credit.assert_awaited_once_with(
            user_id=event.payload.user_id,
            amount=200,
            idempotency_key=event.event_id,
            description=f"Quiz reward: attempt {event.payload.attempt_id}",
        )
        assert result.amount == 200

    async def test_zero_coins_skips_credit(self, service, mock_repo):
        event = make_event(coins=0)
        mock_repo.get_by_user_id.return_value = make_balance(event.payload.user_id, 100)

        result = await service.credit_from_quiz_event(event)

        mock_repo.upsert_credit.assert_not_awaited()
        assert result.amount == 100

    async def test_idempotency_key_equals_event_id(self, service, mock_repo):
        event = make_event(coins=100)
        mock_repo.upsert_credit.return_value = make_balance(event.payload.user_id, 100)

        await service.credit_from_quiz_event(event)

        call_kwargs = mock_repo.upsert_credit.call_args.kwargs
        assert call_kwargs["idempotency_key"] == event.event_id
