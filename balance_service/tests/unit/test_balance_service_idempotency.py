from __future__ import annotations

import uuid
import pytest
from sqlalchemy.exc import SQLAlchemyError
from shared.exceptions import IdempotencyMismatchError

class TestCreditIdempotency:
    async def test_credits_correct_amount(self, service, mock_uow, make_event, make_balance_entity):
        user_id = uuid.uuid4()
        event = make_event(user_id=user_id, coins=200)
        expected_balance = make_balance_entity(user_id, amount=200)
        mock_uow.balances.upsert_credit.return_value = expected_balance

        result = await service.credit_from_quiz_event(event)

        mock_uow.balances.upsert_credit.assert_awaited_once_with(
            user_id=user_id,
            amount=200,
            idempotency_key=event.event_id,
            description=f"Quiz reward: attempt {event.payload.attempt_id}",
        )
        mock_uow.commit.assert_awaited_once()
        assert result.amount == 200
        assert result.user_id == user_id

    async def test_idempotency_key_equals_event_id(self, service, mock_uow, make_event, make_balance_entity):
        user_id = uuid.uuid4()
        event = make_event(user_id=user_id, coins=100)
        mock_uow.balances.upsert_credit.return_value = make_balance_entity(user_id, 100)

        await service.credit_from_quiz_event(event)
        
        call_kwargs = mock_uow.balances.upsert_credit.call_args.kwargs
        assert call_kwargs["idempotency_key"] == event.event_id

    async def test_idempotency_mismatch_fails(self, service, mock_uow, make_event):
        """If repository throws IdempotencyMismatchError, it should propagate."""
        user_id = uuid.uuid4()
        event = make_event(user_id=user_id, coins=100)
        
        mock_uow.balances.upsert_credit.side_effect = IdempotencyMismatchError("Mismatch")
        
        with pytest.raises(IdempotencyMismatchError):
            await service.credit_from_quiz_event(event)
        
        mock_uow.commit.assert_not_awaited()

    async def test_idempotency_retry_success(self, service, mock_uow, make_event, make_balance_entity):
        """Simulate a retry where the first attempt failed during commit but second attempt succeeds."""
        user_id = uuid.uuid4()
        event = make_event(user_id=user_id, coins=100)
        balance = make_balance_entity(user_id, 100)
        
        mock_uow.balances.upsert_credit.return_value = balance
        mock_uow.commit.side_effect = [SQLAlchemyError("Commit failed"), None]
        
        with pytest.raises(SQLAlchemyError):
            await service.credit_from_quiz_event(event)

        res = await service.credit_from_quiz_event(event)
        
        assert res.amount == 100
        assert mock_uow.commit.await_count == 2
        assert mock_uow.balances.upsert_credit.await_count == 2

    async def test_multiple_credits_accumulation(self, service, mock_uow, make_event, make_balance_entity):
        """Simulate a series of rapid credits for the same user."""
        user_id = uuid.uuid4()
        amounts = [10, 20, 30]
        cumulative = 0
        
        def upsert_side_effect(user_id, amount, idempotency_key, description):
            nonlocal cumulative
            cumulative += amount
            return make_balance_entity(user_id, cumulative)
            
        mock_uow.balances.upsert_credit.side_effect = upsert_side_effect
        
        for amt in amounts:
            event = make_event(user_id=user_id, coins=amt)
            res = await service.credit_from_quiz_event(event)
            assert res.amount == cumulative
            
        assert cumulative == 60
        assert mock_uow.commit.await_count == 3

class TestZeroCreditCases:
    async def test_zero_coins_skips_credit(self, service, mock_uow, make_event, make_balance_entity):
        user_id = uuid.uuid4()
        event = make_event(user_id=user_id, coins=0)
        mock_uow.balances.get_by_user_id.return_value = make_balance_entity(user_id, 100)

        result = await service.credit_from_quiz_event(event)

        mock_uow.balances.upsert_credit.assert_not_awaited()
        assert result.amount == 100

    async def test_negative_coins_skips(self, service, mock_uow, make_event, make_balance_entity):
        """Events with zero or negative coins skip the credit operation."""
        user_id = uuid.uuid4()
        event = make_event(user_id=user_id, coins=-50)
        mock_uow.balances.get_by_user_id.return_value = make_balance_entity(user_id, 100)

        result = await service.credit_from_quiz_event(event)

        assert result.amount == 100
        mock_uow.balances.upsert_credit.assert_not_awaited()

    async def test_zero_coins_creates_balance_if_none(self, service, mock_uow, make_event, make_balance_entity):
        """Zero coins event creates initial balance if user has none."""
        user_id = uuid.uuid4()
        event = make_event(user_id=user_id, coins=0)
        mock_uow.balances.get_by_user_id.side_effect = [None, make_balance_entity(user_id, 0)]

        result = await service.credit_from_quiz_event(event)

        assert result.amount == 0
