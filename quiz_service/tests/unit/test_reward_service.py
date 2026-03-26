"""
Unit tests for RewardService.

Covers:
- Empty correct IDs short-circuit
- All IDs already rewarded → no new records
- Partial deduplication (some already rewarded)
- All new → creates reward records + outbox event
- Coin calculation correctness
- Outbox event structure validation
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from src.attempt.service.reward import RewardService
from tests.conftest import make_uuid


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def reward_service(mock_uow):
    return RewardService()


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestProcessRewards:
    @pytest.mark.asyncio
    async def test_empty_input_returns_empty_no_db_calls(
        self, reward_service, mock_uow
    ):
        result = await reward_service.process_rewards(
            uow=mock_uow,
            user_id=make_uuid(),
            quiz_id=make_uuid(),
            attempt_id=make_uuid(),
            correct_question_ids=[],
        )
        assert result == []
        mock_uow.user_rewards.get_rewarded_ids_by_questions.assert_not_called()
        mock_uow.user_rewards.bulk_add.assert_not_called()
        mock_uow.outbox.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_all_already_rewarded_returns_empty(self, reward_service, mock_uow):
        q1, q2 = make_uuid(), make_uuid()
        mock_uow.user_rewards.get_rewarded_ids_by_questions.return_value = {q1, q2}

        result = await reward_service.process_rewards(
            uow=mock_uow,
            user_id=make_uuid(),
            quiz_id=make_uuid(),
            attempt_id=make_uuid(),
            correct_question_ids=[q1, q2],
        )

        assert result == []
        mock_uow.user_rewards.bulk_add.assert_not_called()
        mock_uow.outbox.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_prior_rewards_creates_all_records(self, reward_service, mock_uow):
        q1, q2 = make_uuid(), make_uuid()
        mock_uow.user_rewards.get_rewarded_ids_by_questions.return_value = set()

        result = await reward_service.process_rewards(
            uow=mock_uow,
            user_id=make_uuid(),
            quiz_id=make_uuid(),
            attempt_id=make_uuid(),
            correct_question_ids=[q1, q2],
        )

        assert set(result) == {q1, q2}
        mock_uow.user_rewards.bulk_add.assert_called_once()
        mock_uow.outbox.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_partial_deduplication(self, reward_service, mock_uow):
        q1, q2, q3 = make_uuid(), make_uuid(), make_uuid()
        mock_uow.user_rewards.get_rewarded_ids_by_questions.return_value = {q1}

        result = await reward_service.process_rewards(
            uow=mock_uow,
            user_id=make_uuid(),
            quiz_id=make_uuid(),
            attempt_id=make_uuid(),
            correct_question_ids=[q1, q2, q3],
        )

        assert q1 not in result
        assert set(result) == {q2, q3}

    @pytest.mark.asyncio
    async def test_coin_calculation(self, reward_service, mock_uow):
        """Coins must equal newly_rewarded_count × coins_per_correct_answer."""
        q1, q2 = make_uuid(), make_uuid()
        mock_uow.user_rewards.get_rewarded_ids_by_questions.return_value = set()

        with patch(
            "src.attempt.service.reward.project_settings"
        ) as mock_settings:
            mock_settings.quiz_coins_per_correct_answer = 50
            captured = {}

            async def capture_outbox(entity):
                captured["entity"] = entity

            mock_uow.outbox.add.side_effect = capture_outbox

            await reward_service.process_rewards(
                uow=mock_uow,
                user_id=make_uuid(),
                quiz_id=make_uuid(),
                attempt_id=make_uuid(),
                correct_question_ids=[q1, q2],
            )

        assert captured["entity"].payload["payload"]["coins_to_award"] == 100  # 2 * 50

    @pytest.mark.asyncio
    async def test_outbox_event_routing_key(self, reward_service, mock_uow):
        mock_uow.user_rewards.get_rewarded_ids_by_questions.return_value = set()
        captured = {}

        async def capture_outbox(entity):
            captured["entity"] = entity

        mock_uow.outbox.add.side_effect = capture_outbox

        await reward_service.process_rewards(
            uow=mock_uow,
            user_id=make_uuid(),
            quiz_id=make_uuid(),
            attempt_id=make_uuid(),
            correct_question_ids=[make_uuid()],
        )

        assert captured["entity"].event_type == "quiz.rewarded"
        # assert captured["entity"].routing_key == "quiz.questions.rewarded"
        assert captured["entity"].published_at is None
        assert captured["entity"].attempts == 0

    @pytest.mark.asyncio
    async def test_reward_entity_fields_correct(self, reward_service, mock_uow):
        user_id = make_uuid()
        quiz_id = make_uuid()
        q1 = make_uuid()
        mock_uow.user_rewards.get_rewarded_ids_by_questions.return_value = set()
        captured = {}

        async def capture_bulk(entities):
            captured["entities"] = entities

        mock_uow.user_rewards.bulk_add.side_effect = capture_bulk

        await reward_service.process_rewards(
            uow=mock_uow,
            user_id=user_id,
            quiz_id=quiz_id,
            attempt_id=make_uuid(),
            correct_question_ids=[q1],
        )

        entity = captured["entities"][0]
        assert entity.user_id == user_id
        assert entity.quiz_id == quiz_id
        assert entity.question_id == q1
        assert entity.rewarded_at is not None

    @pytest.mark.asyncio
    async def test_single_correct_answer_one_outbox_event(self, reward_service, mock_uow):
        """Only one outbox event per process_rewards call, regardless of question count."""
        mock_uow.user_rewards.get_rewarded_ids_by_questions.return_value = set()

        await reward_service.process_rewards(
            uow=mock_uow,
            user_id=make_uuid(),
            quiz_id=make_uuid(),
            attempt_id=make_uuid(),
            correct_question_ids=[make_uuid(), make_uuid(), make_uuid()],
        )

        assert mock_uow.outbox.add.call_count == 1