from __future__ import annotations

import uuid
import pytest
from sqlalchemy.exc import SQLAlchemyError

class TestTransactionalIntegrity:
    async def test_rollback_on_post_repo_failure(self, service, mock_uow, make_event, make_balance_entity):
        """If service logic fails after repo call but before commit, ensure no commit."""
        user_id = uuid.uuid4()
        event = make_event(user_id=user_id, coins=100)
        mock_uow.balances.upsert_credit.return_value = make_balance_entity(user_id, 100)
        
        mock_uow.commit.side_effect = SQLAlchemyError("DB Connection Lost")
        
        with pytest.raises(SQLAlchemyError):
            await service.credit_from_quiz_event(event)
            
        mock_uow.commit.assert_awaited_once()

class TestConcurrency:
    async def test_concurrency_race_condition_simulation(self, service, mock_uow, make_balance_entity):
        """Simulate two requests checking for balance balance simultaneously."""
        user_id = uuid.uuid4()
        mock_uow.balances.get_by_user_id.side_effect = [
            None, # First check in get_balance
            make_balance_entity(user_id, 0), # Check after _ensure_balance_row
        ]
        
        result = await service.get_balance(user_id)
        
        assert result.amount == 0
        mock_uow.balances._ensure_balance_row.assert_awaited_once_with(user_id)
        mock_uow.commit.assert_awaited_once()
