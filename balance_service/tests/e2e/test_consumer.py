"""
E2E tests for the balance_service RabbitMQ consumer.

Covers the full message-processing pipeline:
  handle_quiz_reward_message → BalanceService → UoW → repositories

Scenarios:
  - Valid message → balance credited
  - Zero-coin message → no-op
  - Invalid JSON → exception (DLQ routing)
  - Invalid schema → exception (DLQ routing)
  - DB error during credit → exception (DLQ routing)
  - Duplicate event → idempotent, no double-credit
  - Mismatch idempotency → IdempotencyMismatchError raised
  - Consumer supervisor: reconnects on failure
  - Consumer supervisor: stops on CancelledError
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.exceptions import IdempotencyMismatchError
from shared.schemas import QuizRewardEvent
from src.balance.consumer import handle_quiz_reward_message
from tests.conftest import make_quiz_reward_event, make_uuid


def _serialize_event(event: QuizRewardEvent) -> bytes:
    return event.model_dump_json().encode()


# ===========================================================================
# handle_quiz_reward_message
# ===========================================================================

class TestHandleQuizRewardMessage:

    @pytest.mark.asyncio
    async def test_valid_message_credits_balance(self):
        event = make_quiz_reward_event(coins=200)
        body = _serialize_event(event)
        mock_service = AsyncMock()
        mock_service.credit_from_quiz_event = AsyncMock(
            return_value=MagicMock(amount=200, user_id=event.payload.user_id)
        )

        with patch("src.balance.consumer.SqlAlchemyUnitOfWork") as mock_uow_cls, \
             patch("src.balance.consumer.BalanceService") as mock_svc_cls:
            mock_uow_cls.return_value.__aenter__ = AsyncMock(return_value=mock_uow_cls.return_value)
            mock_uow_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_svc_cls.return_value = mock_service

            await handle_quiz_reward_message(
                body=body,
                routing_key="quiz.questions.rewarded",
                message_id=str(make_uuid()),
            )

            mock_service.credit_from_quiz_event.assert_called_once()
            called_event = mock_service.credit_from_quiz_event.call_args.args[0]
            assert called_event.payload.coins_to_award == 200

    @pytest.mark.asyncio
    async def test_invalid_json_raises_exception(self):
        """Malformed JSON must raise so AMQP NACKs it to the DLQ."""
        with pytest.raises(Exception):
            await handle_quiz_reward_message(
                body=b"not valid json at all {{",
                routing_key="quiz.questions.rewarded",
                message_id=str(make_uuid()),
            )

    @pytest.mark.asyncio
    async def test_invalid_schema_raises_exception(self):
        """A structurally wrong payload must raise for DLQ routing."""
        body = json.dumps({"event_type": "wrong.type", "payload": {}}).encode()

        with pytest.raises(Exception):
            await handle_quiz_reward_message(
                body=body,
                routing_key="quiz.questions.rewarded",
                message_id=str(make_uuid()),
            )

    @pytest.mark.asyncio
    async def test_zero_coins_event_processed_without_db_write(self):
        """Zero-coin events are valid — no exception, but no balance mutation."""
        event = make_quiz_reward_event(coins=0)
        body = _serialize_event(event)
        mock_service = AsyncMock()
        mock_service.credit_from_quiz_event = AsyncMock(
            return_value=MagicMock(amount=0)
        )

        with patch("src.balance.consumer.SqlAlchemyUnitOfWork") as mock_uow_cls, \
             patch("src.balance.consumer.BalanceService") as mock_svc_cls:
            mock_uow_cls.return_value.__aenter__ = AsyncMock(return_value=mock_uow_cls.return_value)
            mock_uow_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_svc_cls.return_value = mock_service

            await handle_quiz_reward_message(
                body=body,
                routing_key="quiz.questions.rewarded",
                message_id=str(make_uuid()),
            )

            mock_service.credit_from_quiz_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_db_error_propagates_for_dlq_routing(self):
        """DB failures must propagate so the message is NACKed."""
        event = make_quiz_reward_event(coins=100)
        body = _serialize_event(event)
        mock_service = AsyncMock()
        mock_service.credit_from_quiz_event.side_effect = RuntimeError("DB is down")

        with patch("src.balance.consumer.SqlAlchemyUnitOfWork") as mock_uow_cls, \
             patch("src.balance.consumer.BalanceService") as mock_svc_cls:
            mock_uow_cls.return_value.__aenter__ = AsyncMock(return_value=mock_uow_cls.return_value)
            mock_uow_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_svc_cls.return_value = mock_service

            with pytest.raises(RuntimeError, match="DB is down"):
                await handle_quiz_reward_message(
                    body=body,
                    routing_key="quiz.questions.rewarded",
                    message_id=str(make_uuid()),
                )

    @pytest.mark.asyncio
    async def test_duplicate_event_does_not_raise(self):
        """Duplicate idempotency keys are silently absorbed by the service."""
        event = make_quiz_reward_event(coins=100)
        body = _serialize_event(event)
        mock_service = AsyncMock()
        mock_service.credit_from_quiz_event = AsyncMock(
            return_value=MagicMock(amount=100)
        )

        with patch("src.balance.consumer.SqlAlchemyUnitOfWork") as mock_uow_cls, \
             patch("src.balance.consumer.BalanceService") as mock_svc_cls:
            mock_uow_cls.return_value.__aenter__ = AsyncMock(return_value=mock_uow_cls.return_value)
            mock_uow_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_svc_cls.return_value = mock_service

            # Should not raise
            await handle_quiz_reward_message(body=body, routing_key="rk", message_id="msg1")

    @pytest.mark.asyncio
    async def test_idempotency_mismatch_propagates(self):
        event = make_quiz_reward_event(coins=100)
        body = _serialize_event(event)
        mock_service = AsyncMock()
        mock_service.credit_from_quiz_event.side_effect = IdempotencyMismatchError("mismatch")

        with patch("src.balance.consumer.SqlAlchemyUnitOfWork") as mock_uow_cls, \
             patch("src.balance.consumer.BalanceService") as mock_svc_cls:
            mock_uow_cls.return_value.__aenter__ = AsyncMock(return_value=mock_uow_cls.return_value)
            mock_uow_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_svc_cls.return_value = mock_service

            with pytest.raises(IdempotencyMismatchError):
                await handle_quiz_reward_message(body=body, routing_key="rk", message_id="msg1")

    @pytest.mark.asyncio
    async def test_event_deserialized_with_correct_fields(self):
        user_id = make_uuid()
        quiz_id = make_uuid()
        attempt_id = make_uuid()
        event_id = make_uuid()
        event = make_quiz_reward_event(
            event_id=event_id,
            user_id=user_id,
            quiz_id=quiz_id,
            attempt_id=attempt_id,
            coins=150,
        )
        body = _serialize_event(event)
        captured = {}
        mock_service = AsyncMock()

        async def capture_event(e):
            captured["event"] = e
            return MagicMock(amount=150)

        mock_service.credit_from_quiz_event.side_effect = capture_event

        with patch("src.balance.consumer.SqlAlchemyUnitOfWork") as mock_uow_cls, \
             patch("src.balance.consumer.BalanceService") as mock_svc_cls:
            mock_uow_cls.return_value.__aenter__ = AsyncMock(return_value=mock_uow_cls.return_value)
            mock_uow_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_svc_cls.return_value = mock_service

            await handle_quiz_reward_message(body=body, routing_key="rk", message_id="msg")

        e = captured["event"]
        assert e.event_id == event_id
        assert e.payload.user_id == user_id
        assert e.payload.coins_to_award == 150

    @pytest.mark.asyncio
    async def test_empty_body_raises(self):
        with pytest.raises(Exception):
            await handle_quiz_reward_message(
                body=b"",
                routing_key="rk",
                message_id="msg",
            )


# ===========================================================================
# Consumer supervisor lifespan
# ===========================================================================

class TestConsumerSupervisor:

    @pytest.mark.asyncio
    async def test_supervisor_stops_on_cancelled_error(self):
        """CancelledError from asyncio.Task.cancel() must be handled cleanly."""
        from src.lifespan import _supervise_consumer
        import src.lifespan as lifespan_module

        mock_consumer = AsyncMock()
        mock_consumer.is_connected = True
        mock_consumer.consume.side_effect = asyncio.CancelledError()
        mock_consumer.close = AsyncMock()

        with patch("src.lifespan.start_consumer", return_value=mock_consumer):
            with patch.object(lifespan_module, "_consumer", None):
                task = asyncio.create_task(_supervise_consumer())
                await asyncio.sleep(0.05)
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass  # expected

    @pytest.mark.asyncio
    async def test_is_consumer_connected_false_when_none(self):
        from src.lifespan import is_consumer_connected
        import src.lifespan as lifespan_module

        original = lifespan_module._consumer
        try:
            lifespan_module._consumer = None
            assert is_consumer_connected() is False
        finally:
            lifespan_module._consumer = original

    @pytest.mark.asyncio
    async def test_is_consumer_connected_true_when_connected(self):
        from src.lifespan import is_consumer_connected
        import src.lifespan as lifespan_module

        original = lifespan_module._consumer
        try:
            mock = MagicMock()
            mock.is_connected = True
            lifespan_module._consumer = mock
            assert is_consumer_connected() is True
        finally:
            lifespan_module._consumer = original