from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.attempt.enum import AttemptStatusEnum
from src.attempt.entities import OutboxEventEntity, QuizAttemptEntity
from src.quiz.entities import QuestionEntity, QuizEntity
from src.quiz.enum import QuestionType


def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def make_uuid() -> uuid.UUID:
    return uuid.uuid4()


def make_quiz_attempt(
    *,
    status: AttemptStatusEnum = AttemptStatusEnum.IN_PROGRESS,
    user_id: uuid.UUID | None = None,
    quiz_id: uuid.UUID | None = None,
    attempt_id: uuid.UUID | None = None,
) -> QuizAttemptEntity:
    now = utcnow()
    return QuizAttemptEntity(
        id=attempt_id or make_uuid(),
        quiz_id=quiz_id or make_uuid(),
        user_id=user_id or make_uuid(),
        status=status,
        score=None,
        total_questions=None,
        started_at=now,
        updated_at=now,
        completed_at=None,
    )


def make_quiz(
    *,
    quiz_id: uuid.UUID | None = None,
    is_active: bool = True,
    questions: list[QuestionEntity] | None = None,
) -> QuizEntity:
    qs = questions or []
    return QuizEntity(
        id=quiz_id or make_uuid(),
        title={"en": "Test Quiz", "de": "Test Quiz DE"},
        description={"en": "A quiz for testing"},
        is_active=is_active,
        question_count=len(qs),
        questions=qs,
    )


def make_question(
    *,
    question_id: uuid.UUID | None = None,
    q_type: QuestionType = QuestionType.SINGLE_CHOICE,
    correct_id: uuid.UUID | None = None,
) -> QuestionEntity:
    cid = correct_id or make_uuid()
    payload: dict = {}
    if q_type == QuestionType.SINGLE_CHOICE:
        payload = {
            "correct_id": str(cid),
            "options": [
                {"id": str(cid), "text": {"en": "Correct"}},
                {"id": str(make_uuid()), "text": {"en": "Wrong"}},
            ],
        }
    elif q_type == QuestionType.MULTIPLE_CHOICE:
        payload = {
            "correct_ids": [str(cid)],
            "options": [
                {"id": str(cid), "text": {"en": "Correct"}},
                {"id": str(make_uuid()), "text": {"en": "Wrong"}},
            ],
        }
    elif q_type == QuestionType.FILL_GAP:
        payload = {"correct_answers": ["paris", "Paris"]}
    elif q_type == QuestionType.MATCHING:
        left = make_uuid()
        right = make_uuid()
        payload = {"pairs": [{"left_id": str(left), "right_id": str(right)}]}
    return QuestionEntity(
        id=question_id or make_uuid(),
        type=q_type,
        order_index=0,
        text={"en": "Test question?"},
        payload=payload,
    )


def make_outbox_event(*, event_id: uuid.UUID | None = None) -> OutboxEventEntity:
    return OutboxEventEntity(
        id=event_id or make_uuid(),
        event_type="quiz.rewarded",
        routing_key="quiz.questions.rewarded",
        payload={"user_id": str(make_uuid()), "coins": 100},
        created_at=utcnow(),
        published_at=None,
        attempts=0,
    )


# ---------------------------------------------------------------------------
# Repository mocks
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_quiz_attempt_repo():
    repo = AsyncMock()
    repo.add = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.get_by_id_for_update = AsyncMock(return_value=None)
    repo.update = AsyncMock()
    repo.mark_abandoned = AsyncMock()
    repo.bulk_mark_abandoned = AsyncMock(return_value=0)
    return repo


@pytest.fixture
def mock_quiz_repo():
    repo = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.get_all_active = AsyncMock(return_value=[])
    repo.count_active = AsyncMock(return_value=0)
    repo.add = AsyncMock()
    repo.update = AsyncMock(return_value=True)
    repo.set_active_status = AsyncMock(return_value=True)
    return repo


@pytest.fixture
def mock_question_repo():
    repo = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.get_by_ids = AsyncMock(return_value=[])      # ← was missing
    repo.get_by_quiz_id = AsyncMock(return_value=[])
    repo.add = AsyncMock()
    repo.update = AsyncMock(return_value=True)
    repo.delete = AsyncMock(return_value=True)
    return repo


@pytest.fixture
def mock_user_answers_repo():
    repo = AsyncMock()
    repo.bulk_add = AsyncMock()
    repo.upsert_draft = AsyncMock()
    repo.bulk_upsert_graded_answers = AsyncMock()     # ← was missing
    return repo


@pytest.fixture
def mock_user_rewards_repo():
    repo = AsyncMock()
    repo.get_rewarded_ids_by_questions = AsyncMock(return_value=set())
    repo.bulk_add = AsyncMock()
    return repo


@pytest.fixture
def mock_outbox_repo():
    repo = AsyncMock()
    repo.add = AsyncMock()
    repo.get_pending_events = AsyncMock(return_value=[])
    repo.mark_published = AsyncMock()
    repo.increment_attempts = AsyncMock()
    return repo


@pytest.fixture
def mock_uow(
    mock_quiz_attempt_repo,
    mock_quiz_repo,
    mock_question_repo,
    mock_user_answers_repo,
    mock_user_rewards_repo,
    mock_outbox_repo,
):
    uow = AsyncMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)
    uow.commit = AsyncMock()
    uow.rollback = AsyncMock()
    uow.quiz_attempts = mock_quiz_attempt_repo
    uow.quizzes = mock_quiz_repo
    uow.questions = mock_question_repo
    uow.user_answers = mock_user_answers_repo
    uow.user_rewards = mock_user_rewards_repo
    uow.outbox = mock_outbox_repo
    return uow


@pytest.fixture
def mock_grading_service():
    svc = MagicMock()
    svc.check_answer = MagicMock(return_value=True)
    return svc


@pytest.fixture
def mock_reward_service():
    svc = AsyncMock()
    svc.process_rewards = AsyncMock(return_value=[])
    return svc


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock()
    redis.delete = AsyncMock()
    redis.scan_iter = AsyncMock(return_value=iter([]))
    redis.ping = AsyncMock(return_value=True)
    return redis


@pytest.fixture
def mock_publisher():
    pub = AsyncMock()
    pub.publish = AsyncMock()
    pub.connect = AsyncMock()
    pub.close = AsyncMock()
    return pub