from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestHandleQuizRewardMessage:
    async def test_valid_message_credits_balance(self, make_event):
        """A valid message deserializes and calls credit_from_quiz_event."""
        event = make_event(coins=100)
        body = json.dumps(event.model_dump(mode="json")).encode()

        mock_uow = AsyncMock()
        mock_uow.__aenter__.return_value = mock_uow
        mock_uow.__aexit__.return_value = False

        mock_balance = MagicMock(amount=100)

        with patch("src.balance.consumer.SqlAlchemyUnitOfWork", return_value=mock_uow), \
             patch("src.balance.consumer.BalanceService") as MockService:

            mock_service_instance = AsyncMock()
            mock_service_instance.credit_from_quiz_event.return_value = mock_balance
            MockService.return_value = mock_service_instance

            from src.balance.consumer import handle_quiz_reward_message

            await handle_quiz_reward_message(
                body=body,
                routing_key="quiz.questions.rewarded",
                message_id=str(uuid.uuid4()),
            )

            mock_service_instance.credit_from_quiz_event.assert_awaited_once()

    async def test_invalid_json_raises(self):
        """Invalid JSON body raises an exception for DLQ routing."""
        from src.balance.consumer import handle_quiz_reward_message

        with pytest.raises(Exception):
            await handle_quiz_reward_message(
                body=b"not valid json {{{",
                routing_key="quiz.questions.rewarded",
                message_id=str(uuid.uuid4()),
            )

    async def test_invalid_schema_raises(self):
        """Valid JSON but invalid schema raises for DLQ routing."""
        from src.balance.consumer import handle_quiz_reward_message

        body = json.dumps({"wrong_field": "data"}).encode()

        with pytest.raises(Exception):
            await handle_quiz_reward_message(
                body=body,
                routing_key="quiz.questions.rewarded",
                message_id=str(uuid.uuid4()),
            )
