"""
Unit tests for AttemptService.

Covers:
- start_attempt: inactive quiz, not found, happy path
- auto_save_answer: not found, wrong user, wrong status, happy path
- submit_attempt: grading, rewards, duplicate submission, forbidden
- abandon_attempt: state transitions
- _validate_attempt_access: all failure branches
- _grade_answers: missing question IDs
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.attempt.dto import (
    AnswerItemDTO,
    AutoSaveRequestDTO,
    SingleChoicePayload,
    SubmitAttemptDTO,
)
from src.attempt.enum import AttemptStatusEnum
from src.attempt.service.attempt import AttemptService
from shared.exceptions import (
    AttemptAlreadyCompletedException,
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from tests.conftest import make_quiz, make_quiz_attempt, make_question, make_uuid
from src.quiz.enum import QuestionType


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def service(mock_uow, mock_reward_service, mock_grading_service):
    return AttemptService(
        uow=mock_uow,
        reward_service=mock_reward_service,
        grading_service=mock_grading_service,
    )


def _make_submit_dto(question_id: uuid.UUID, selected_id: uuid.UUID) -> SubmitAttemptDTO:
    return SubmitAttemptDTO(
        answers=[
            AnswerItemDTO(
                question_id=question_id,
                answer_payload=SingleChoicePayload(
                    question_type="single_choice",
                    selected_id=selected_id,
                ),
            )
        ]
    )


def _make_auto_save_dto(question_id: uuid.UUID, selected_id: uuid.UUID) -> AutoSaveRequestDTO:
    return AutoSaveRequestDTO(
        answer=AnswerItemDTO(
            question_id=question_id,
            answer_payload=SingleChoicePayload(
                question_type="single_choice",
                selected_id=selected_id,
            ),
        )
    )


# ─────────────────────────────────────────────────────────────────────────────
# start_attempt
# ─────────────────────────────────────────────────────────────────────────────

class TestStartAttempt:
    @pytest.mark.asyncio
    async def test_quiz_not_found_raises(self, service, mock_uow):
        mock_uow.quizzes.get_by_id.return_value = None
        with pytest.raises(NotFoundException):
            await service.start_attempt(quiz_id=make_uuid(), user_id=make_uuid())

    @pytest.mark.asyncio
    async def test_inactive_quiz_raises(self, service, mock_uow):
        quiz = make_quiz(is_active=False)
        mock_uow.quizzes.get_by_id.return_value = quiz
        with pytest.raises(NotFoundException):
            await service.start_attempt(quiz_id=quiz.id, user_id=make_uuid())

    @pytest.mark.asyncio
    async def test_happy_path_returns_dto(self, service, mock_uow):
        quiz = make_quiz(is_active=True)
        mock_uow.quizzes.get_by_id.return_value = quiz
        user_id = make_uuid()

        result = await service.start_attempt(quiz_id=quiz.id, user_id=user_id)

        assert result.quiz_id == quiz.id
        assert result.user_id == user_id
        assert result.attempt_id is not None
        mock_uow.quiz_attempts.add.assert_called_once()
        mock_uow.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_attempt_persisted_with_in_progress_status(self, service, mock_uow):
        quiz = make_quiz(is_active=True)
        mock_uow.quizzes.get_by_id.return_value = quiz
        captured = {}

        async def capture_add(entity):
            captured["entity"] = entity

        mock_uow.quiz_attempts.add.side_effect = capture_add
        await service.start_attempt(quiz_id=quiz.id, user_id=make_uuid())

        assert captured["entity"].status == AttemptStatusEnum.IN_PROGRESS
        assert captured["entity"].score is None
        assert captured["entity"].completed_at is None


# ─────────────────────────────────────────────────────────────────────────────
# auto_save_answer
# ─────────────────────────────────────────────────────────────────────────────

class TestAutoSaveAnswer:
    @pytest.mark.asyncio
    async def test_attempt_not_found_raises(self, service, mock_uow):
        mock_uow.quiz_attempts.get_by_id_for_update.return_value = None
        with pytest.raises(NotFoundException):
            await service.auto_save_answer(
                attempt_id=make_uuid(),
                user_id=make_uuid(),
                request=_make_auto_save_dto(make_uuid(), make_uuid()),
            )

    @pytest.mark.asyncio
    async def test_wrong_user_raises_forbidden(self, service, mock_uow):
        attempt = make_quiz_attempt(user_id=make_uuid())
        mock_uow.quiz_attempts.get_by_id_for_update.return_value = attempt
        different_user = make_uuid()

        with pytest.raises(ForbiddenException):
            await service.auto_save_answer(
                attempt_id=attempt.id,
                user_id=different_user,
                request=_make_auto_save_dto(make_uuid(), make_uuid()),
            )

    @pytest.mark.asyncio
    async def test_completed_attempt_raises(self, service, mock_uow):
        user_id = make_uuid()
        attempt = make_quiz_attempt(
            user_id=user_id, status=AttemptStatusEnum.COMPLETED
        )
        mock_uow.quiz_attempts.get_by_id_for_update.return_value = attempt

        with pytest.raises(AttemptAlreadyCompletedException):
            await service.auto_save_answer(
                attempt_id=attempt.id,
                user_id=user_id,
                request=_make_auto_save_dto(make_uuid(), make_uuid()),
            )

    @pytest.mark.asyncio
    async def test_abandoned_attempt_raises(self, service, mock_uow):
        user_id = make_uuid()
        attempt = make_quiz_attempt(
            user_id=user_id, status=AttemptStatusEnum.ABANDONED
        )
        mock_uow.quiz_attempts.get_by_id_for_update.return_value = attempt

        with pytest.raises(AttemptAlreadyCompletedException):
            await service.auto_save_answer(
                attempt_id=attempt.id,
                user_id=user_id,
                request=_make_auto_save_dto(make_uuid(), make_uuid()),
            )

    @pytest.mark.asyncio
    async def test_happy_path_upserts_draft(self, service, mock_uow):
        user_id = make_uuid()
        attempt = make_quiz_attempt(user_id=user_id)
        mock_uow.quiz_attempts.get_by_id_for_update.return_value = attempt
        question_id = make_uuid()

        await service.auto_save_answer(
            attempt_id=attempt.id,
            user_id=user_id,
            request=_make_auto_save_dto(question_id, make_uuid()),
        )

        mock_uow.user_answers.upsert_draft.assert_called_once()
        mock_uow.quiz_attempts.update.assert_called_once()
        mock_uow.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_draft_has_no_is_correct(self, service, mock_uow):
        """Draft answers must have is_correct=None — grading happens on submit only."""
        user_id = make_uuid()
        attempt = make_quiz_attempt(user_id=user_id)
        mock_uow.quiz_attempts.get_by_id_for_update.return_value = attempt
        captured = {}

        async def capture(entity):
            captured["entity"] = entity

        mock_uow.user_answers.upsert_draft.side_effect = capture

        await service.auto_save_answer(
            attempt_id=attempt.id,
            user_id=user_id,
            request=_make_auto_save_dto(make_uuid(), make_uuid()),
        )

        assert captured["entity"].is_correct is None


# ─────────────────────────────────────────────────────────────────────────────
# abandon_attempt
# ─────────────────────────────────────────────────────────────────────────────

class TestAbandonAttempt:
    @pytest.mark.asyncio
    async def test_not_found_raises(self, service, mock_uow):
        mock_uow.quiz_attempts.get_by_id_for_update.return_value = None
        with pytest.raises(NotFoundException):
            await service.abandon_attempt(attempt_id=make_uuid(), user_id=make_uuid())

    @pytest.mark.asyncio
    async def test_wrong_user_raises(self, service, mock_uow):
        attempt = make_quiz_attempt(user_id=make_uuid())
        mock_uow.quiz_attempts.get_by_id_for_update.return_value = attempt
        with pytest.raises(ForbiddenException):
            await service.abandon_attempt(attempt_id=attempt.id, user_id=make_uuid())

    @pytest.mark.asyncio
    async def test_already_completed_raises(self, service, mock_uow):
        user_id = make_uuid()
        attempt = make_quiz_attempt(user_id=user_id, status=AttemptStatusEnum.COMPLETED)
        mock_uow.quiz_attempts.get_by_id_for_update.return_value = attempt
        with pytest.raises(AttemptAlreadyCompletedException):
            await service.abandon_attempt(attempt_id=attempt.id, user_id=user_id)

    @pytest.mark.asyncio
    async def test_marks_as_abandoned(self, service, mock_uow):
        user_id = make_uuid()
        attempt = make_quiz_attempt(user_id=user_id)
        mock_uow.quiz_attempts.get_by_id_for_update.return_value = attempt
        captured = {}

        async def capture(entity):
            captured["entity"] = entity

        mock_uow.quiz_attempts.update.side_effect = capture

        await service.abandon_attempt(attempt_id=attempt.id, user_id=user_id)

        assert captured["entity"].status == AttemptStatusEnum.ABANDONED
        mock_uow.commit.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# submit_attempt
# ─────────────────────────────────────────────────────────────────────────────

class TestSubmitAttempt:
    @pytest.mark.asyncio
    async def test_not_found_raises(self, service, mock_uow):
        mock_uow.quiz_attempts.get_by_id_for_update.return_value = None
        with pytest.raises(NotFoundException):
            await service.submit_attempt(
                attempt_id=make_uuid(),
                user_id=make_uuid(),
                request=_make_submit_dto(make_uuid(), make_uuid()),
            )

    @pytest.mark.asyncio
    async def test_double_submit_raises(self, service, mock_uow):
        user_id = make_uuid()
        attempt = make_quiz_attempt(user_id=user_id, status=AttemptStatusEnum.COMPLETED)
        mock_uow.quiz_attempts.get_by_id_for_update.return_value = attempt

        with pytest.raises(AttemptAlreadyCompletedException):
            await service.submit_attempt(
                attempt_id=attempt.id,
                user_id=user_id,
                request=_make_submit_dto(make_uuid(), make_uuid()),
            )

    @pytest.mark.asyncio
    async def test_invalid_question_ids_raises(self, service, mock_uow):
        user_id = make_uuid()
        attempt = make_quiz_attempt(user_id=user_id)
        mock_uow.quiz_attempts.get_by_id_for_update.return_value = attempt
        # Return empty questions — submitted IDs don't match
        mock_uow.questions.get_by_ids.return_value = []

        with pytest.raises(ValidationException):
            await service.submit_attempt(
                attempt_id=attempt.id,
                user_id=user_id,
                request=_make_submit_dto(make_uuid(), make_uuid()),
            )

    @pytest.mark.asyncio
    async def test_happy_path_sets_completed(self, service, mock_uow, mock_grading_service):
        user_id = make_uuid()
        question_id = make_uuid()
        correct_id = make_uuid()
        attempt = make_quiz_attempt(user_id=user_id)
        question = make_question(question_id=question_id, q_type=QuestionType.SINGLE_CHOICE, correct_id=correct_id)

        mock_uow.quiz_attempts.get_by_id_for_update.return_value = attempt
        mock_uow.questions.get_by_ids.return_value = [question]
        mock_grading_service.check_answer.return_value = True

        result = await service.submit_attempt(
            attempt_id=attempt.id,
            user_id=user_id,
            request=_make_submit_dto(question_id, correct_id),
        )

        assert result.score == 1
        assert result.total_questions == 1
        mock_uow.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_all_wrong_gives_zero_score(self, service, mock_uow, mock_grading_service):
        user_id = make_uuid()
        question_id = make_uuid()
        attempt = make_quiz_attempt(user_id=user_id)
        question = make_question(question_id=question_id)

        mock_uow.quiz_attempts.get_by_id_for_update.return_value = attempt
        mock_uow.questions.get_by_ids.return_value = [question]
        mock_grading_service.check_answer.return_value = False

        result = await service.submit_attempt(
            attempt_id=attempt.id,
            user_id=user_id,
            request=_make_submit_dto(question_id, make_uuid()),
        )

        assert result.score == 0
        assert result.coins_awarded == 0

    @pytest.mark.asyncio
    async def test_already_rewarded_questions_excluded_from_coins(
        self, service, mock_uow, mock_grading_service, mock_reward_service
    ):
        user_id = make_uuid()
        question_id = make_uuid()
        attempt = make_quiz_attempt(user_id=user_id)
        question = make_question(question_id=question_id)

        mock_uow.quiz_attempts.get_by_id_for_update.return_value = attempt
        mock_uow.questions.get_by_ids.return_value = [question]
        mock_grading_service.check_answer.return_value = True
        # Previously rewarded — no new reward IDs returned
        mock_reward_service.process_rewards.return_value = []

        result = await service.submit_attempt(
            attempt_id=attempt.id,
            user_id=user_id,
            request=_make_submit_dto(question_id, make_uuid()),
        )

        assert result.coins_awarded == 0
        assert result.question_results[0].was_already_rewarded is True

    @pytest.mark.asyncio
    async def test_attempt_status_set_to_completed(self, service, mock_uow, mock_grading_service):
        user_id = make_uuid()
        question_id = make_uuid()
        attempt = make_quiz_attempt(user_id=user_id)
        question = make_question(question_id=question_id)

        mock_uow.quiz_attempts.get_by_id_for_update.return_value = attempt
        mock_uow.questions.get_by_ids.return_value = [question]
        mock_grading_service.check_answer.return_value = True
        captured = {}

        async def capture(entity):
            captured["entity"] = entity

        mock_uow.quiz_attempts.update.side_effect = capture

        await service.submit_attempt(
            attempt_id=attempt.id,
            user_id=user_id,
            request=_make_submit_dto(question_id, make_uuid()),
        )

        assert captured["entity"].status == AttemptStatusEnum.COMPLETED
        assert captured["entity"].completed_at is not None

    @pytest.mark.asyncio
    async def test_rollback_on_exception(self, service, mock_uow, mock_grading_service):
        """If anything raises after the UoW entry, __aexit__ must trigger rollback."""
        user_id = make_uuid()
        attempt = make_quiz_attempt(user_id=user_id)
        mock_uow.quiz_attempts.get_by_id_for_update.return_value = attempt
        # Force a crash
        mock_uow.questions.get_by_ids.side_effect = RuntimeError("db down")

        with pytest.raises(RuntimeError):
            await service.submit_attempt(
                attempt_id=attempt.id,
                user_id=user_id,
                request=_make_submit_dto(make_uuid(), make_uuid()),
            )

        mock_uow.__aexit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_forbidden_user_on_submit(self, service, mock_uow):
        attempt = make_quiz_attempt(user_id=make_uuid())
        mock_uow.quiz_attempts.get_by_id_for_update.return_value = attempt

        with pytest.raises(ForbiddenException):
            await service.submit_attempt(
                attempt_id=attempt.id,
                user_id=make_uuid(),  # different user
                request=_make_submit_dto(make_uuid(), make_uuid()),
            )


# ─────────────────────────────────────────────────────────────────────────────
# _grade_answers (internal, tested via submit)
# ─────────────────────────────────────────────────────────────────────────────

class TestGradeAnswers:
    @pytest.mark.asyncio
    async def test_missing_questions_raises_validation(self, service, mock_uow):
        """Submitting question IDs not in the database is rejected."""
        user_id = make_uuid()
        attempt = make_quiz_attempt(user_id=user_id)
        mock_uow.quiz_attempts.get_by_id_for_update.return_value = attempt
        # DB returns a question with a different ID than submitted
        mock_uow.questions.get_by_ids.return_value = [
            make_question(question_id=make_uuid())
        ]

        with pytest.raises(ValidationException) as exc_info:
            await service.submit_attempt(
                attempt_id=attempt.id,
                user_id=user_id,
                request=_make_submit_dto(make_uuid(), make_uuid()),
            )

        assert "Invalid question IDs" in str(exc_info.value.message)