"""
Unit tests for BalanceService covering all business-logic paths:

  get_balance
    - existing user returns current amount
    - new user gets lazy-created zero balance
    - commit is called on creation
    - db error propagates

  credit_from_quiz_event
    - normal flow: transaction inserted, balance upserted, commit called
    - zero coins skips db and returns current balance
    - negative coins skips db (same guard)
    - duplicate key, same amount: balance returned, no double-credit
    - duplicate key, different amount: IdempotencyMismatchError raised
    - new user first reward: balance created atomically
    - very large coin amount handled
    - db error during insert propagates and rolls back

  _resolve_duplicate_event
    - no existing txn (None returned by repo): safe ignore, returns balance
    - existing txn same amount: safe ignore
    - existing txn different amount: raises IdempotencyMismatchError
    - no balance after duplicate: upserts zero

  get_transactions
    - empty history
    - single page full
    - offset / page math
    - page 2 uses correct offset
    - page_size boundary at 1
    - total > page_size returns correct metadata
"""
from __future__ import annotations

import pytest

from shared.exceptions import IdempotencyMismatchError
from src.balance.service.balance import BalanceService
from tests.conftest import (
    make_balance,
    make_quiz_reward_event,
    make_transaction,
    make_uuid,
    utcnow,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_service(mock_uow) -> BalanceService:
    return BalanceService(uow=mock_uow)


# ===========================================================================
# get_balance
# ===========================================================================

class TestGetBalance:

    @pytest.mark.asyncio
    async def test_existing_user_returns_balance(self, mock_uow, mock_balance_repo):
        user_id = make_uuid()
        balance = make_balance(user_id=user_id, amount=750)
        mock_balance_repo.get_by_user_id.return_value = balance

        result = await _make_service(mock_uow).get_balance(user_id)

        assert result.user_id == user_id
        assert result.amount == 750
        mock_balance_repo.upsert_amount.assert_not_called()
        mock_uow.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_new_user_creates_zero_balance(self, mock_uow, mock_balance_repo):
        user_id = make_uuid()
        mock_balance_repo.get_by_user_id.return_value = None
        created = make_balance(user_id=user_id, amount=0)
        mock_balance_repo.upsert_amount.return_value = created

        result = await _make_service(mock_uow).get_balance(user_id)

        assert result.amount == 0
        mock_balance_repo.upsert_amount.assert_called_once_with(user_id, 0)
        mock_uow.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_new_user_commit_is_mandatory(self, mock_uow, mock_balance_repo):
        """Omitting commit for a new balance would leave the row in limbo."""
        mock_balance_repo.get_by_user_id.return_value = None
        mock_balance_repo.upsert_amount.return_value = make_balance(amount=0)

        await _make_service(mock_uow).get_balance(make_uuid())

        mock_uow.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_balance_amount_zero_is_valid(self, mock_uow, mock_balance_repo):
        user_id = make_uuid()
        mock_balance_repo.get_by_user_id.return_value = make_balance(user_id=user_id, amount=0)

        result = await _make_service(mock_uow).get_balance(user_id)

        assert result.amount == 0
        mock_balance_repo.upsert_amount.assert_not_called()

    @pytest.mark.asyncio
    async def test_db_error_propagates(self, mock_uow, mock_balance_repo):
        mock_balance_repo.get_by_user_id.side_effect = RuntimeError("connection lost")

        with pytest.raises(RuntimeError, match="connection lost"):
            await _make_service(mock_uow).get_balance(make_uuid())

    @pytest.mark.asyncio
    async def test_uow_context_entered(self, mock_uow, mock_balance_repo):
        mock_balance_repo.get_by_user_id.return_value = make_balance()

        await _make_service(mock_uow).get_balance(make_uuid())

        mock_uow.__aenter__.assert_called_once()
        mock_uow.__aexit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_response_dto_fields_populated(self, mock_uow, mock_balance_repo):
        user_id = make_uuid()
        now = utcnow()
        bal = make_balance(user_id=user_id, amount=1234)
        bal.updated_at = now
        mock_balance_repo.get_by_user_id.return_value = bal

        result = await _make_service(mock_uow).get_balance(user_id)

        assert result.user_id == user_id
        assert result.amount == 1234
        assert result.updated_at == now


# ===========================================================================
# credit_from_quiz_event
# ===========================================================================

class TestCreditFromQuizEvent:

    @pytest.mark.asyncio
    async def test_normal_flow_inserts_transaction_and_credits_balance(
        self, mock_uow, mock_balance_repo, mock_transaction_repo
    ):
        user_id = make_uuid()
        event = make_quiz_reward_event(user_id=user_id, coins=200)
        tx = make_transaction(user_id=user_id, amount=200, idempotency_key=event.event_id)
        mock_transaction_repo.insert_idempotent.return_value = tx
        updated_balance = make_balance(user_id=user_id, amount=700)
        mock_balance_repo.upsert_amount.return_value = updated_balance

        result = await _make_service(mock_uow).credit_from_quiz_event(event)

        mock_transaction_repo.insert_idempotent.assert_called_once_with(
            user_id=user_id,
            amount=200,
            idempotency_key=event.event_id,
            description=f"Quiz reward: attempt {event.payload.attempt_id}",
        )
        mock_balance_repo.upsert_amount.assert_called_once_with(user_id=user_id, amount=200)
        mock_uow.commit.assert_called_once()
        assert result.amount == 700

    @pytest.mark.asyncio
    async def test_zero_coins_skips_db_writes(
        self, mock_uow, mock_balance_repo, mock_transaction_repo
    ):
        """Zero-coin events must be a no-op — no transaction, no balance mutation."""
        user_id = make_uuid()
        event = make_quiz_reward_event(user_id=user_id, coins=0)
        # get_balance will be called for zero-coin path
        mock_balance_repo.get_by_user_id.return_value = make_balance(user_id=user_id, amount=500)

        result = await _make_service(mock_uow).credit_from_quiz_event(event)

        mock_transaction_repo.insert_idempotent.assert_not_called()
        mock_balance_repo.upsert_amount.assert_not_called()
        assert result.amount == 500

    @pytest.mark.asyncio
    async def test_negative_coins_treated_as_zero(
        self, mock_uow, mock_balance_repo, mock_transaction_repo
    ):
        """Negative coin values should be skipped identically to zero."""
        user_id = make_uuid()
        event = make_quiz_reward_event(user_id=user_id, coins=-50)
        mock_balance_repo.get_by_user_id.return_value = make_balance(user_id=user_id, amount=300)

        result = await _make_service(mock_uow).credit_from_quiz_event(event)

        mock_transaction_repo.insert_idempotent.assert_not_called()
        assert result.amount == 300

    @pytest.mark.asyncio
    async def test_duplicate_event_same_amount_returns_balance_without_credit(
        self, mock_uow, mock_balance_repo, mock_transaction_repo
    ):
        """ON CONFLICT returns None → duplicate detected → balance unchanged."""
        user_id = make_uuid()
        event_id = make_uuid()
        event = make_quiz_reward_event(user_id=user_id, event_id=event_id, coins=100)
        mock_transaction_repo.insert_idempotent.return_value = None  # duplicate
        existing_tx = make_transaction(user_id=user_id, amount=100, idempotency_key=event_id)
        mock_transaction_repo.get_by_idempotency_key.return_value = existing_tx
        mock_balance_repo.get_by_user_id.return_value = make_balance(user_id=user_id, amount=400)

        result = await _make_service(mock_uow).credit_from_quiz_event(event)

        mock_balance_repo.upsert_amount.assert_not_called()
        mock_uow.commit.assert_not_called()
        assert result.amount == 400

    @pytest.mark.asyncio
    async def test_duplicate_event_different_amount_raises_mismatch(
        self, mock_uow, mock_transaction_repo
    ):
        """Same idempotency key but different amount is a data-integrity violation."""
        event_id = make_uuid()
        event = make_quiz_reward_event(event_id=event_id, coins=200)
        mock_transaction_repo.insert_idempotent.return_value = None
        existing_tx = make_transaction(amount=100, idempotency_key=event_id)  # different!
        mock_transaction_repo.get_by_idempotency_key.return_value = existing_tx

        with pytest.raises(IdempotencyMismatchError):
            await _make_service(mock_uow).credit_from_quiz_event(event)

    @pytest.mark.asyncio
    async def test_new_user_gets_balance_created_atomically(
        self, mock_uow, mock_balance_repo, mock_transaction_repo
    ):
        """First-time reward for a brand-new user must create balance + transaction."""
        user_id = make_uuid()
        event = make_quiz_reward_event(user_id=user_id, coins=100)
        tx = make_transaction(user_id=user_id, amount=100, idempotency_key=event.event_id)
        mock_transaction_repo.insert_idempotent.return_value = tx
        new_balance = make_balance(user_id=user_id, amount=100)
        mock_balance_repo.upsert_amount.return_value = new_balance

        result = await _make_service(mock_uow).credit_from_quiz_event(event)

        assert result.amount == 100
        mock_uow.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_very_large_coin_amount_handled(
        self, mock_uow, mock_balance_repo, mock_transaction_repo
    ):
        event = make_quiz_reward_event(coins=10_000_000)
        tx = make_transaction(amount=10_000_000, idempotency_key=event.event_id)
        mock_transaction_repo.insert_idempotent.return_value = tx
        mock_balance_repo.upsert_amount.return_value = make_balance(amount=10_000_000)

        result = await _make_service(mock_uow).credit_from_quiz_event(event)

        assert result.amount == 10_000_000

    @pytest.mark.asyncio
    async def test_db_error_during_insert_propagates(
        self, mock_uow, mock_transaction_repo
    ):
        event = make_quiz_reward_event(coins=100)
        mock_transaction_repo.insert_idempotent.side_effect = RuntimeError("DB dead")

        with pytest.raises(RuntimeError, match="DB dead"):
            await _make_service(mock_uow).credit_from_quiz_event(event)

    @pytest.mark.asyncio
    async def test_db_error_during_balance_upsert_propagates(
        self, mock_uow, mock_balance_repo, mock_transaction_repo
    ):
        event = make_quiz_reward_event(coins=100)
        tx = make_transaction(amount=100, idempotency_key=event.event_id)
        mock_transaction_repo.insert_idempotent.return_value = tx
        mock_balance_repo.upsert_amount.side_effect = RuntimeError("constraint error")

        with pytest.raises(RuntimeError, match="constraint error"):
            await _make_service(mock_uow).credit_from_quiz_event(event)

    @pytest.mark.asyncio
    async def test_uow_aexit_called_on_exception(
        self, mock_uow, mock_transaction_repo
    ):
        event = make_quiz_reward_event(coins=100)
        mock_transaction_repo.insert_idempotent.side_effect = Exception("boom")

        with pytest.raises(Exception):
            await _make_service(mock_uow).credit_from_quiz_event(event)

        mock_uow.__aexit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_idempotency_key_is_event_id(
        self, mock_uow, mock_balance_repo, mock_transaction_repo
    ):
        event = make_quiz_reward_event(coins=50)
        tx = make_transaction(amount=50, idempotency_key=event.event_id)
        mock_transaction_repo.insert_idempotent.return_value = tx
        mock_balance_repo.upsert_amount.return_value = make_balance(amount=50)

        await _make_service(mock_uow).credit_from_quiz_event(event)

        call_kwargs = mock_transaction_repo.insert_idempotent.call_args
        assert call_kwargs.kwargs["idempotency_key"] == event.event_id

    @pytest.mark.asyncio
    async def test_description_contains_attempt_id(
        self, mock_uow, mock_balance_repo, mock_transaction_repo
    ):
        event = make_quiz_reward_event(coins=50)
        tx = make_transaction(amount=50, idempotency_key=event.event_id)
        mock_transaction_repo.insert_idempotent.return_value = tx
        mock_balance_repo.upsert_amount.return_value = make_balance(amount=50)

        await _make_service(mock_uow).credit_from_quiz_event(event)

        desc = mock_transaction_repo.insert_idempotent.call_args.kwargs["description"]
        assert str(event.payload.attempt_id) in desc


# ===========================================================================
# _resolve_duplicate_event
# ===========================================================================

class TestResolveDuplicateEventWithinUow:

    @pytest.mark.asyncio
    async def test_no_existing_transaction_safe_ignore(
        self, mock_uow, mock_balance_repo, mock_transaction_repo
    ):
        """None returned from repo (race condition — record not yet visible) is safe."""
        user_id = make_uuid()
        mock_transaction_repo.get_by_idempotency_key.return_value = None
        mock_balance_repo.get_by_user_id.return_value = make_balance(user_id=user_id, amount=200)

        service = _make_service(mock_uow)
        result = await service._resolve_duplicate_event(
            user_id=user_id,
            event_id=make_uuid(),
            expected_amount=100,
        )

        assert result.amount == 200
        mock_balance_repo.upsert_amount.assert_not_called()

    @pytest.mark.asyncio
    async def test_existing_transaction_matching_amount_safe_ignore(
        self, mock_uow, mock_balance_repo, mock_transaction_repo
    ):
        user_id = make_uuid()
        event_id = make_uuid()
        existing_tx = make_transaction(user_id=user_id, amount=100, idempotency_key=event_id)
        mock_transaction_repo.get_by_idempotency_key.return_value = existing_tx
        mock_balance_repo.get_by_user_id.return_value = make_balance(user_id=user_id, amount=300)

        service = _make_service(mock_uow)
        result = await service._resolve_duplicate_event(
            user_id=user_id,
            event_id=event_id,
            expected_amount=100,
        )

        assert result.amount == 300

    @pytest.mark.asyncio
    async def test_existing_transaction_different_amount_raises(
        self, mock_uow, mock_transaction_repo
    ):
        event_id = make_uuid()
        existing_tx = make_transaction(amount=50, idempotency_key=event_id)
        mock_transaction_repo.get_by_idempotency_key.return_value = existing_tx

        service = _make_service(mock_uow)
        with pytest.raises(IdempotencyMismatchError):
            await service._resolve_duplicate_event(
                user_id=make_uuid(),
                event_id=event_id,
                expected_amount=999,  # differs from stored 50
            )

    @pytest.mark.asyncio
    async def test_no_balance_for_user_creates_zero(
        self, mock_uow, mock_balance_repo, mock_transaction_repo
    ):
        user_id = make_uuid()
        mock_transaction_repo.get_by_idempotency_key.return_value = None
        mock_balance_repo.get_by_user_id.return_value = None  # user has no balance yet
        created = make_balance(user_id=user_id, amount=0)
        mock_balance_repo.upsert_amount.return_value = created

        service = _make_service(mock_uow)
        result = await service._resolve_duplicate_event(
            user_id=user_id,
            event_id=make_uuid(),
            expected_amount=100,
        )

        mock_balance_repo.upsert_amount.assert_called_once_with(user_id, 0)
        mock_uow.commit.assert_called_once()
        assert result.amount == 0


# ===========================================================================
# get_transactions
# ===========================================================================

class TestGetTransactions:

    @pytest.mark.asyncio
    async def test_empty_history_returns_empty_list(self, mock_uow, mock_transaction_repo):
        mock_transaction_repo.get_paginated_by_user.return_value = []
        mock_transaction_repo.count_by_user.return_value = 0

        result = await _make_service(mock_uow).get_transactions(user_id=make_uuid(), page=1, page_size=50)

        assert result.items == []
        assert result.total == 0
        assert result.page == 1
        assert result.page_size == 50

    @pytest.mark.asyncio
    async def test_single_page_returns_all_items(self, mock_uow, mock_transaction_repo):
        user_id = make_uuid()
        txs = [make_transaction(user_id=user_id) for _ in range(5)]
        mock_transaction_repo.get_paginated_by_user.return_value = txs
        mock_transaction_repo.count_by_user.return_value = 5

        result = await _make_service(mock_uow).get_transactions(user_id=user_id, page=1, page_size=50)

        assert len(result.items) == 5
        assert result.total == 5

    @pytest.mark.asyncio
    async def test_page_2_uses_correct_offset(self, mock_uow, mock_transaction_repo):
        user_id = make_uuid()
        mock_transaction_repo.get_paginated_by_user.return_value = []
        mock_transaction_repo.count_by_user.return_value = 100

        await _make_service(mock_uow).get_transactions(user_id=user_id, page=3, page_size=10)

        mock_transaction_repo.get_paginated_by_user.assert_called_once_with(
            user_id=user_id, limit=10, offset=20
        )

    @pytest.mark.asyncio
    async def test_page_metadata_correct(self, mock_uow, mock_transaction_repo):
        mock_transaction_repo.get_paginated_by_user.return_value = [make_transaction()]
        mock_transaction_repo.count_by_user.return_value = 150

        result = await _make_service(mock_uow).get_transactions(
            user_id=make_uuid(), page=2, page_size=50
        )

        assert result.page == 2
        assert result.page_size == 50
        assert result.total == 150

    @pytest.mark.asyncio
    async def test_transaction_dto_fields_mapped_correctly(self, mock_uow, mock_transaction_repo):
        user_id = make_uuid()
        tx = make_transaction(user_id=user_id, amount=250, description="Quiz reward: attempt XYZ")
        mock_transaction_repo.get_paginated_by_user.return_value = [tx]
        mock_transaction_repo.count_by_user.return_value = 1

        result = await _make_service(mock_uow).get_transactions(user_id=user_id)

        item = result.items[0]
        assert item.user_id == user_id
        assert item.amount == 250
        assert item.description == "Quiz reward: attempt XYZ"
        assert item.type == "credit"

    @pytest.mark.asyncio
    async def test_page_size_of_1(self, mock_uow, mock_transaction_repo):
        txs = [make_transaction()]
        mock_transaction_repo.get_paginated_by_user.return_value = txs
        mock_transaction_repo.count_by_user.return_value = 100

        result = await _make_service(mock_uow).get_transactions(
            user_id=make_uuid(), page=1, page_size=1
        )

        assert len(result.items) == 1
        mock_transaction_repo.get_paginated_by_user.assert_called_once_with(
            user_id=mock_uow.transactions.get_paginated_by_user.call_args.kwargs["user_id"],
            limit=1,
            offset=0,
        )

    @pytest.mark.asyncio
    async def test_first_page_offset_is_zero(self, mock_uow, mock_transaction_repo):
        mock_transaction_repo.get_paginated_by_user.return_value = []
        mock_transaction_repo.count_by_user.return_value = 0

        await _make_service(mock_uow).get_transactions(user_id=make_uuid(), page=1, page_size=25)

        mock_transaction_repo.get_paginated_by_user.assert_called_once_with(
            user_id=mock_uow.transactions.get_paginated_by_user.call_args.kwargs["user_id"],
            limit=25,
            offset=0,
        )

    @pytest.mark.asyncio
    async def test_db_error_propagates(self, mock_uow, mock_transaction_repo):
        mock_transaction_repo.get_paginated_by_user.side_effect = RuntimeError("timeout")

        with pytest.raises(RuntimeError, match="timeout"):
            await _make_service(mock_uow).get_transactions(user_id=make_uuid())