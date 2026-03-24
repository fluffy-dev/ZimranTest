from __future__ import annotations

import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.anyio
class TestBalanceFlowE2E:
    async def test_complete_balance_journey(
        self, client: AsyncClient, mock_uow_e2e, make_balance_entity, make_event, make_transaction_entity
    ):
        """
        Scenario:
        1. User checks balance for the first time -> Initialized to 0.
        2. User receives a quiz reward -> Updated to 100.
        3. User checks balance again -> Returns 100.
        4. User checks transaction history -> Shows the 100 credit.
        """
        user_id = uuid.uuid4()
        headers = {"X-User-ID": str(user_id)}
        
        # 1. Initial balance check (Mock: None then 0 after ensure)
        mock_uow_e2e.balances.get_by_user_id.side_effect = [
            None, 
            make_balance_entity(user_id, 0)
        ]
        
        resp = await client.get("/api/v1/balance", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["amount"] == 0
        
        # Verify initialisation called
        mock_uow_e2e.balances._ensure_balance_row.assert_awaited_once_with(user_id)
        mock_uow_e2e.commit.assert_awaited_once()
        
        # 2. Simulate Quiz Reward (Service called via internal flow or mocked here)
        # For a true E2E we should ideally trigger the message consumer, 
        # but for API testing we verify the GET /balance consistency.
        
        reward_amount = 100
        mock_uow_e2e.balances.get_by_user_id.side_effect = None
        mock_uow_e2e.balances.get_by_user_id.return_value = make_balance_entity(user_id, reward_amount)
        
        # 3. Check balance again
        resp = await client.get("/api/v1/balance", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["amount"] == reward_amount
        
        # 4. Check transaction history
        mock_uow_e2e.balances.get_transactions.return_value = [
            make_transaction_entity(user_id, reward_amount)
        ]
        mock_uow_e2e.balances.get_transaction_count.return_value = 1
        
        resp = await client.get("/api/v1/balance/transactions", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["amount"] == reward_amount

    async def test_concurrent_balance_requests(self, client: AsyncClient, mock_uow_e2e, make_balance_entity):
        """Simulate rapid fire requests from the same user to ensure no internal errors."""
        import asyncio
        user_id = uuid.uuid4()
        headers = {"X-User-ID": str(user_id)}
        
        mock_uow_e2e.balances.get_by_user_id.return_value = make_balance_entity(user_id, 500)
        
        tasks = [client.get("/api/v1/balance", headers=headers) for _ in range(10)]
        responses = await asyncio.gather(*tasks)
        
        for r in responses:
            assert r.status_code == 200
            assert r.json()["amount"] == 500
            
        assert mock_uow_e2e.balances.get_by_user_id.await_count == 10

    async def test_duplicate_transaction_idempotency_flow(
        self, client: AsyncClient, mock_uow_e2e, make_balance_entity, make_event
    ):
        """Simulate two identical events arriving and ensuring service handles it."""
        user_id = uuid.uuid4()
        event = make_event(user_id=user_id, coins=100)
        headers = {"X-User-ID": str(user_id)}
        
        from shared.exceptions import IdempotencyMismatchError
        
        # Mocking the first call to succeed, second to return same balance (already exists in real repo)
        balance = make_balance_entity(user_id, 100)
        mock_uow_e2e.balances.upsert_credit.return_value = balance
        
        # We simulate the consumer call (service.credit_from_quiz_event)
        from src.balance.dependencies.service import BalanceService
        service = BalanceService(uow=mock_uow_e2e)
        
        res1 = await service.credit_from_quiz_event(event)
        assert res1.amount == 100
        
        # Second call with same event
        res2 = await service.credit_from_quiz_event(event)
        assert res2.amount == 100
        
        assert mock_uow_e2e.commit.await_count == 2
        assert mock_uow_e2e.balances.upsert_credit.await_count == 2

    async def test_extensive_history_pagination(
        self, client: AsyncClient, mock_uow_e2e, make_transaction_entity
    ):
        """Verify complex pagination across multiple pages of history."""
        user_id = uuid.uuid4()
        headers = {"X-User-ID": str(user_id)}
        
        # Mock 105 transactions
        all_txns = [make_transaction_entity(user_id, i) for i in range(105)]
        
        def get_txns_mock(user_id, limit, offset):
            return all_txns[offset : offset + limit]
            
        mock_uow_e2e.balances.get_transactions.side_effect = get_txns_mock
        mock_uow_e2e.balances.get_transaction_count.return_value = 105
        
        # Fetch Page 1 (0-20)
        resp = await client.get("/api/v1/balance/transactions?page=1&page_size=20", headers=headers)
        data = resp.json()
        assert data["total"] == 105
        assert len(data["items"]) == 20
        assert data["items"][0]["amount"] == 0
        
        # Fetch Page 6 (100-105)
        resp = await client.get("/api/v1/balance/transactions?page=6&page_size=20", headers=headers)
        data = resp.json()
        assert len(data["items"]) == 5
        assert data["items"][0]["amount"] == 100
