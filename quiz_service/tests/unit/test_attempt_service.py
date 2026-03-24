from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.attempt.enum import AttemptStatusEnum
from src.quiz.models.quiz import QuestionType
from src.attempt.dto import SubmitAttemptDTO, AnswerItemDTO
from src.attempt.service.attempt import AttemptService
from src.config.project import settings
from src.attempt.service.grading import GradingService


def make_attempt(
    quiz_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    status: str = AttemptStatusEnum.IN_PROGRESS,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        quiz_id=quiz_id or uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        status=status,
        answers=[],
    )


def make_question(q_id: uuid.UUID, q_type: str = QuestionType.SINGLE_CHOICE) -> SimpleNamespace:
    return SimpleNamespace(
        id=q_id,
        type=q_type,
        payload={"correct_id": "a", "options": [{"id": "a"}, {"id": "b"}]},
    )


@pytest.fixture
def mock_quiz_repo():
    return AsyncMock()


@pytest.fixture
def mock_attempt_repo():
    return AsyncMock()


@pytest.fixture
def mock_outbox_repo():
    return AsyncMock()


@pytest.fixture
def mock_uow(mock_quiz_repo, mock_attempt_repo, mock_outbox_repo):
    uow = AsyncMock()
    uow.quizzes = mock_quiz_repo
    uow.attempts = mock_attempt_repo
    uow.outbox = mock_outbox_repo
    uow.commit = AsyncMock()
    uow.rollback = AsyncMock()
    
    # Mock async context manager
    uow.__aenter__.return_value = uow
    uow.__aexit__.return_value = None
    return uow


@pytest.fixture
def service(mock_uow):
    grading = GradingService()
    return AttemptService(
        uow=mock_uow,
        grading_service=grading,
    )


class TestSubmitAttempt:
    async def test_correct_score_calculated(
        self, service, mock_quiz_repo, mock_attempt_repo, mock_outbox_repo, mock_uow
    ):
        user_id = uuid.uuid4()
        q1_id = uuid.uuid4()
        q2_id = uuid.uuid4()

        attempt = make_attempt(user_id=user_id)
        mock_attempt_repo.get_by_id.return_value = attempt
        mock_quiz_repo.get_questions_by_ids.return_value = [
            make_question(q1_id),
            make_question(q2_id),
        ]
        mock_attempt_repo.get_already_rewarded_question_ids.return_value = set()
        mock_attempt_repo.bulk_insert_rewarded_questions.return_value = None
        mock_attempt_repo.bulk_save_answers.return_value = None

        completed = make_attempt(user_id=user_id)
        completed.status = AttemptStatusEnum.COMPLETED
        completed.score = 2
        completed.total_questions = 2
        mock_attempt_repo.complete_attempt.return_value = completed

        request = SubmitAttemptDTO(
            answers=[
                AnswerItemDTO(question_id=q1_id, answer_payload={"selected_id": "a"}),
                AnswerItemDTO(question_id=q2_id, answer_payload={"selected_id": "a"}),
            ]
        )

        result = await service.submit_attempt(
            attempt_id=attempt.id, user_id=user_id, request=request
        )

        assert result.score == 2
        assert result.total_questions == 2
        assert result.coins_awarded == 2 * settings.quiz_coins_per_correct_answer
        mock_uow.commit.assert_awaited_once()

    async def test_no_reward_for_already_rewarded_question(
        self, service, mock_quiz_repo, mock_attempt_repo, mock_outbox_repo, mock_uow
    ):
        user_id = uuid.uuid4()
        q1_id = uuid.uuid4()

        attempt = make_attempt(user_id=user_id)
        mock_attempt_repo.get_by_id.return_value = attempt
        mock_quiz_repo.get_questions_by_ids.return_value = [make_question(q1_id)]
        mock_attempt_repo.get_already_rewarded_question_ids.return_value = {q1_id}
        mock_attempt_repo.bulk_save_answers.return_value = None

        completed = make_attempt(user_id=user_id)
        completed.status = AttemptStatusEnum.COMPLETED
        completed.score = 1
        completed.total_questions = 1
        mock_attempt_repo.complete_attempt.return_value = completed

        request = SubmitAttemptDTO(
            answers=[AnswerItemDTO(question_id=q1_id, answer_payload={"selected_id": "a"})]
        )

        result = await service.submit_attempt(
            attempt_id=attempt.id, user_id=user_id, request=request
        )

        assert result.score == 1
        assert result.coins_awarded == 0
        assert result.question_results[0].was_already_rewarded is True
        mock_outbox_repo.insert_event.assert_not_awaited()
        mock_uow.commit.assert_awaited_once()

    async def test_raises_on_completed_attempt(
        self, service, mock_attempt_repo
    ):
        from shared.exceptions import AttemptAlreadyCompletedException

        user_id = uuid.uuid4()
        attempt = make_attempt(user_id=user_id, status=AttemptStatusEnum.COMPLETED)
        mock_attempt_repo.get_by_id.return_value = attempt

        request = SubmitAttemptDTO(
            answers=[AnswerItemDTO(question_id=uuid.uuid4(), answer_payload={"selected_id": "a"})]
        )

        with pytest.raises(AttemptAlreadyCompletedException):
            await service.submit_attempt(
                attempt_id=attempt.id, user_id=user_id, request=request
            )
