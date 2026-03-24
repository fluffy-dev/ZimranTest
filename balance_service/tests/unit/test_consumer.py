from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.schemas import QuizRewardEvent, QuizRewardPayload


def make_event(coins: int = 200) -> QuizRewardEvent:
    """Creates a valid QuizRewardEvent for testing."""
    return QuizRewardEvent(
        payload=QuizRewardPayload(
            user_id=uuid.uuid4(),
            quiz_id=uuid.uuid4(),
            attempt_id=uuid.uuid4(),
            newly_rewarded_question_ids=[uuid.uuid4()],
            coins_to_award=coins,
        ),
    )


class TestHandleQuizRewardMessage:
    async def test_valid_message_credits_balance(self):
        """A valid message deserializes and calls credit_from_quiz_event via UoW."""
        event = make_event(coins=100)
        body = json.dumps(event.model_dump(mode="json")).encode()

        mock_balance = MagicMock(amount=100)

        with patch("src.balance.consumer.SqlAlchemyUnitOfWork") as MockUOW, \
             patch("src.balance.consumer.BalanceService") as MockService:

            mock_uow_instance = MagicMock()
            MockUOW.return_value = mock_uow_instance
            
            mock_service_instance = AsyncMock()
            mock_service_instance.credit_from_quiz_event.return_value = mock_balance
            MockService.return_value = mock_service_instance

            from src.balance.consumer import handle_quiz_reward_message

            await handle_quiz_reward_message(
                body=body,
                routing_key="quiz.questions.rewarded",
                message_id=str(uuid.uuid4()),
            )

            MockUOW.assert_called_once()
            MockService.assert_called_once_with(mock_uow_instance)
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
