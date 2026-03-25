"""
Unit tests for OutboxProcessor (lifespan.py).

Covers:
- No events → sleep without publishing
- Successful publish → marks published, commits
- Broker ConnectionError → rollback, stops batch, returns
- Broker TimeoutError → same as ConnectionError
- Generic exception → increments attempts, continues batch
- Batch continues after single generic failure
- Cancellation signal handled gracefully
- Published_at is set on success
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from src.lifespan import OutboxProcessor
from tests.conftest import make_outbox_event, make_uuid


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def processor(mock_publisher):
    proc = OutboxProcessor(publisher=mock_publisher)
    # Replace session factory with a context manager mock
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    mock_factory = MagicMock(return_value=mock_session)
    proc._session_factory = mock_factory
    proc._mock_session = mock_session
    return proc


# ─────────────────────────────────────────────────────────────────────────────
# _process_next_batch
# ─────────────────────────────────────────────────────────────────────────────

class TestProcessNextBatch:
    @pytest.mark.asyncio
    async def test_no_events_returns_zero(self, processor):
        with patch(
            "src.lifespan.OutboxEventRepository"
        ) as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo.get_pending_events.return_value = []
            mock_repo_cls.return_value = mock_repo

            result = await processor._process_next_batch()
            assert result == 0

    @pytest.mark.asyncio
    async def test_successful_publish_marks_published(self, processor, mock_publisher):
        event = make_outbox_event()

        with patch("src.lifespan.OutboxEventRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo.get_pending_events.return_value = [event]
            mock_repo_cls.return_value = mock_repo

            result = await processor._process_next_batch()

            mock_publisher.publish.assert_called_once()
            mock_repo.mark_published.assert_called_once_with(event)
            processor._mock_session.commit.assert_called()
            assert event.published_at is not None
            assert result == 1

    @pytest.mark.asyncio
    async def test_connection_error_stops_batch(self, processor, mock_publisher):
        event1 = make_outbox_event()
        event2 = make_outbox_event()
        mock_publisher.publish.side_effect = ConnectionError("Broker down")

        with patch("src.lifespan.OutboxEventRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo.get_pending_events.return_value = [event1, event2]
            mock_repo_cls.return_value = mock_repo

            result = await processor._process_next_batch()

            # Should have stopped after first failure
            assert mock_publisher.publish.call_count == 1
            processor._mock_session.rollback.assert_called()

    @pytest.mark.asyncio
    async def test_timeout_error_stops_batch(self, processor, mock_publisher):
        event = make_outbox_event()
        mock_publisher.publish.side_effect = TimeoutError("Timeout")

        with patch("src.lifespan.OutboxEventRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo.get_pending_events.return_value = [event]
            mock_repo_cls.return_value = mock_repo

            await processor._process_next_batch()
            processor._mock_session.rollback.assert_called()

    @pytest.mark.asyncio
    async def test_generic_exception_increments_attempts_continues(
        self, processor, mock_publisher
    ):
        event1 = make_outbox_event()
        event2 = make_outbox_event()

        call_count = 0

        async def publish_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Serialization error")

        mock_publisher.publish.side_effect = publish_side_effect

        with patch("src.lifespan.OutboxEventRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo.get_pending_events.return_value = [event1, event2]
            mock_repo_cls.return_value = mock_repo

            await processor._process_next_batch()

            # event1 failed → increment_attempts called
            mock_repo.increment_attempts.assert_called_once_with(event1)
            # event2 succeeded → mark_published called
            mock_repo.mark_published.assert_called_once_with(event2)

    @pytest.mark.asyncio
    async def test_published_at_timestamp_set_on_success(self, processor, mock_publisher):
        event = make_outbox_event()
        assert event.published_at is None

        with patch("src.lifespan.OutboxEventRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo.get_pending_events.return_value = [event]
            mock_repo_cls.return_value = mock_repo

            await processor._process_next_batch()

        assert event.published_at is not None
        assert isinstance(event.published_at, datetime)

    @pytest.mark.asyncio
    async def test_payload_serialized_as_json_bytes(self, processor, mock_publisher):
        event = make_outbox_event()
        event.payload = {"user_id": "123", "coins": 50}
        captured_body = {}

        async def capture_publish(routing_key, body, message_id):
            captured_body["body"] = body

        mock_publisher.publish.side_effect = capture_publish

        with patch("src.lifespan.OutboxEventRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo.get_pending_events.return_value = [event]
            mock_repo_cls.return_value = mock_repo

            await processor._process_next_batch()

        parsed = json.loads(captured_body["body"])
        assert parsed["user_id"] == "123"
        assert parsed["coins"] == 50


# ─────────────────────────────────────────────────────────────────────────────
# run (cancellation)
# ─────────────────────────────────────────────────────────────────────────────

class TestRun:
    @pytest.mark.asyncio
    async def test_cancellation_is_handled_gracefully(self, processor):
        """CancelledError during run must not propagate."""
        call_count = 0

        async def fake_process():
            nonlocal call_count
            call_count += 1
            raise asyncio.CancelledError()

        processor._process_next_batch = fake_process

        # Should not raise
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await processor.run()

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_sleeps_when_no_events(self, processor):
        call_count = 0

        async def fake_process():
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise asyncio.CancelledError()
            return 0  # no events

        processor._process_next_batch = fake_process

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with patch(
                "src.lifespan.outbox_settings"
            ) as mock_settings:
                mock_settings.poll_interval = 5.0
                await processor.run()

            mock_sleep.assert_called_with(5.0)

    @pytest.mark.asyncio
    async def test_no_sleep_when_events_processed(self, processor):
        """When events are processed, the loop should not sleep."""
        call_count = 0

        async def fake_process():
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise asyncio.CancelledError()
            return 5  # events processed

        processor._process_next_batch = fake_process

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await processor.run()

        mock_sleep.assert_not_called()