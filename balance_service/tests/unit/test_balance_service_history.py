from __future__ import annotations

import uuid
import pytest

class TestGetTransactions:
    async def test_pagination_offset(self, service, mock_uow):
        """Page 2 with page_size 10 calculates offset=10."""
        user_id = uuid.uuid4()
        mock_uow.balances.get_transactions.return_value = []
        mock_uow.balances.get_transaction_count.return_value = 0

        await service.get_transactions(user_id, page=2, page_size=10)

        mock_uow.balances.get_transactions.assert_awaited_once_with(
            user_id=user_id, limit=10, offset=10
        )

    async def test_returns_transaction_list(self, service, mock_uow, make_transaction_entity):
        """Returns list of transactions from repository."""
        user_id = uuid.uuid4()
        txns = [make_transaction_entity(user_id, 100), make_transaction_entity(user_id, 200)]
        mock_uow.balances.get_transactions.return_value = txns
        mock_uow.balances.get_transaction_count.return_value = 2

        result = await service.get_transactions(user_id)

        assert len(result.items) == 2
        assert result.items[0].amount == 100
        assert result.items[1].amount == 200
        assert result.total == 2

    async def test_extremely_large_credit(self, service, mock_uow, make_event, make_balance_entity):
        """Verify handling of very large credit amounts."""
        user_id = uuid.uuid4()
        large_amount = 10**12 # 1 trillion
        event = make_event(user_id=user_id, coins=large_amount)
        
        mock_uow.balances.upsert_credit.return_value = make_balance_entity(user_id, large_amount)
        
        res = await service.credit_from_quiz_event(event)
        assert res.amount == large_amount
