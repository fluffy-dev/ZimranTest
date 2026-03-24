from __future__ import annotations

import uuid
import pytest

class TestGetBalance:
    async def test_returns_existing_balance(self, service, mock_uow, make_balance_entity):
        """Returns balance if user already has one."""
        user_id = uuid.uuid4()
        mock_uow.balances.get_by_user_id.return_value = make_balance_entity(user_id, 500)

        result = await service.get_balance(user_id)

        assert result.amount == 500
        mock_uow.balances.upsert_credit.assert_not_awaited()

    async def test_creates_initial_balance_when_none(self, service, mock_uow, make_balance_entity):
        """Creates a zero balance when user has no existing record."""
        user_id = uuid.uuid4()
        mock_uow.balances.get_by_user_id.side_effect = [None, make_balance_entity(user_id, 0)]

        result = await service.get_balance(user_id)

        assert result.amount == 0
        mock_uow.balances._ensure_balance_row.assert_awaited_once_with(user_id)
        mock_uow.commit.assert_awaited_once()

    async def test_unrecoverable_ensure_failure(self, service, mock_uow):
        """Test the safety check when balance still None after ensure."""
        user_id = uuid.uuid4()
        mock_uow.balances.get_by_user_id.return_value = None
        
        with pytest.raises(RuntimeError) as exc:
            await service.get_balance(user_id)
            
        assert "Failed to ensure balance row" in str(exc.value)

class TestUserIsolation:
    async def test_multi_user_isolation(self, service, mock_uow, make_balance_entity):
        """Ensure balance operations for one user don't affect another (logic level)."""
        user_a = uuid.uuid4()
        user_b = uuid.uuid4()
        
        mock_uow.balances.get_by_user_id.side_effect = lambda uid: {
            user_a: make_balance_entity(user_a, 100),
            user_b: make_balance_entity(user_b, 200),
        }.get(uid)
        
        res_a = await service.get_balance(user_a)
        res_b = await service.get_balance(user_b)
        
        assert res_a.user_id == user_a
        assert res_a.amount == 100
        assert res_b.user_id == user_b
        assert res_b.amount == 200
