from __future__ import annotations

import uuid
from datetime import datetime, timezone

from shared.schemas import EventEnvelope, QuizRewardEvent, QuizRewardPayload


class TestEventEnvelope:
    def test_defaults_generated(self):
        """Event envelope generates UUID and timezone-aware timestamp by default."""
        envelope = EventEnvelope(
            event_type="test.event",
            payload={"key": "value"},
        )

        assert isinstance(envelope.event_id, uuid.UUID)
        assert envelope.schema_version == "1.0"
        assert envelope.occurred_at.tzinfo is not None

    def test_custom_event_id(self):
        """Custom event_id is preserved."""
        custom_id = uuid.uuid4()
        envelope = EventEnvelope(
            event_id=custom_id,
            event_type="test.event",
            payload={},
        )

        assert envelope.event_id == custom_id

    def test_occurred_at_is_utc(self):
        """Timestamp defaults to UTC."""
        envelope = EventEnvelope(event_type="test", payload={})

        assert envelope.occurred_at.tzinfo == timezone.utc


class TestQuizRewardEvent:
    def test_serialization_roundtrip(self):
        """QuizRewardEvent can be serialized and deserialized."""
        user_id = uuid.uuid4()
        quiz_id = uuid.uuid4()
        attempt_id = uuid.uuid4()
        q_ids = [uuid.uuid4(), uuid.uuid4()]

        event = QuizRewardEvent(
            payload=QuizRewardPayload(
                user_id=user_id,
                quiz_id=quiz_id,
                attempt_id=attempt_id,
                newly_rewarded_question_ids=q_ids,
                coins_to_award=200,
            ),
        )

        data = event.model_dump(mode="json")
        restored = QuizRewardEvent.model_validate(data)

        assert restored.event_type == "quiz.questions.rewarded"
        assert restored.payload.coins_to_award == 200
        assert len(restored.payload.newly_rewarded_question_ids) == 2
        assert restored.payload.user_id == user_id

    def test_event_type_is_set(self):
        """QuizRewardEvent has correct event_type."""
        event = QuizRewardEvent(
            payload=QuizRewardPayload(
                user_id=uuid.uuid4(),
                quiz_id=uuid.uuid4(),
                attempt_id=uuid.uuid4(),
                newly_rewarded_question_ids=[],
                coins_to_award=0,
            ),
        )

        assert event.event_type == "quiz.questions.rewarded"

    def test_payload_fields(self):
        """All payload fields are accessible."""
        user_id = uuid.uuid4()
        event = QuizRewardEvent(
            payload=QuizRewardPayload(
                user_id=user_id,
                quiz_id=uuid.uuid4(),
                attempt_id=uuid.uuid4(),
                newly_rewarded_question_ids=[uuid.uuid4()],
                coins_to_award=100,
            ),
        )

        assert event.payload.user_id == user_id
        assert event.payload.coins_to_award == 100
        assert len(event.payload.newly_rewarded_question_ids) == 1
