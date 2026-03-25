"""
Unit tests for QuizLocalizationService and QuizService.

Covers:
- Locale resolution: exact match, fallback to 'en', fallback to first key
- Payload sanitization: options stripping correct keys, matching pairs stripping answers
- fill_gap returns empty payload (no options to leak)
- QuizService CRUD: create, get, set_status, append/update/delete question
- NotFoundException paths
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from src.quiz.dto import CreateQuizDTO, CreateQuestionDTO
from src.quiz.entities import QuestionEntity, QuizEntity
from src.quiz.enum import QuestionType
from src.quiz.service.localization import QuizLocalizationService
from src.quiz.service.quiz import QuizService
from shared.exceptions import NotFoundException
from tests.conftest import make_quiz, make_question, make_uuid


# ─────────────────────────────────────────────────────────────────────────────
# QuizLocalizationService
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def loc():
    return QuizLocalizationService()


class TestExtractText:
    def test_exact_locale(self, loc):
        assert loc.extract_text({"en": "Hello", "de": "Hallo"}, "de") == "Hallo"

    def test_falls_back_to_en(self, loc):
        assert loc.extract_text({"en": "Hello"}, "fr") == "Hello"

    def test_falls_back_to_first_key(self, loc):
        assert loc.extract_text({"de": "Hallo"}, "fr") == "Hallo"

    def test_empty_map_returns_empty_string(self, loc):
        assert loc.extract_text({}, "en") == ""

    def test_none_map_returns_empty_string(self, loc):
        assert loc.extract_text(None, "en") == ""

    def test_case_insensitive_locale_lookup(self, loc):
        assert loc.extract_text({"en": "Hello"}, "EN") == "Hello"

    def test_strips_whitespace_from_locale(self, loc):
        assert loc.extract_text({"en": "Hello"}, " en ") == "Hello"


class TestSanitizePayload:
    def test_single_choice_strips_correct_id(self, loc):
        payload = {
            "correct_id": str(uuid.uuid4()),
            "options": [
                {"id": "1", "text": {"en": "Option A"}},
            ],
        }
        result = loc.sanitize_question_payload(payload, QuestionType.SINGLE_CHOICE, "en")
        assert "correct_id" not in result
        assert "options" in result
        assert result["options"][0]["text"] == "Option A"

    def test_multiple_choice_strips_correct_ids(self, loc):
        payload = {
            "correct_ids": ["1", "2"],
            "options": [
                {"id": "1", "text": {"en": "A"}},
                {"id": "2", "text": {"en": "B"}},
            ],
        }
        result = loc.sanitize_question_payload(payload, QuestionType.MULTIPLE_CHOICE, "en")
        assert "correct_ids" not in result
        assert len(result["options"]) == 2

    def test_fill_gap_returns_empty_payload(self, loc):
        payload = {"correct_answers": ["paris"]}
        result = loc.sanitize_question_payload(payload, QuestionType.FILL_GAP, "en")
        assert "correct_answers" not in result
        assert result == {}

    def test_matching_strips_correct_pairing(self, loc):
        payload = {
            "pairs": [
                {
                    "pair_id": "p1",
                    "left": {"en": "Left"},
                    "right": {"en": "Right"},
                    "correct_match": "r1",  # should be stripped
                }
            ]
        }
        result = loc.sanitize_question_payload(payload, QuestionType.MATCHING, "en")
        assert "correct_match" not in result["pairs"][0]
        assert result["pairs"][0]["left"] == "Left"
        assert result["pairs"][0]["right"] == "Right"

    def test_options_localized_per_locale(self, loc):
        payload = {
            "options": [
                {"id": "1", "text": {"en": "English", "de": "Deutsch"}},
            ]
        }
        result = loc.sanitize_question_payload(payload, QuestionType.SINGLE_CHOICE, "de")
        assert result["options"][0]["text"] == "Deutsch"


class TestToQuizDetailDto:
    def test_questions_sorted_by_order_index(self, loc):
        q1 = make_question()
        q2 = make_question()
        q1.order_index = 5  # type: ignore[attr-defined]  # dataclass slot mutation not ideal
        # Use object creation directly
        q1 = QuestionEntity(
            id=uuid.uuid4(), type=QuestionType.SINGLE_CHOICE, order_index=5,
            text={"en": "Q5"}, payload={"options": [], "correct_id": "x"},
        )
        q2 = QuestionEntity(
            id=uuid.uuid4(), type=QuestionType.SINGLE_CHOICE, order_index=1,
            text={"en": "Q1"}, payload={"options": [], "correct_id": "x"},
        )
        quiz = make_quiz(questions=[q1, q2])
        dto = loc.to_quiz_detail_dto(quiz, "en")
        assert dto.questions[0].order_index == 1
        assert dto.questions[1].order_index == 5

    def test_none_description_handled(self, loc):
        quiz = QuizEntity(
            id=uuid.uuid4(),
            title={"en": "Test"},
            description=None,
            is_active=True,
            questions=[],
        )
        dto = loc.to_quiz_detail_dto(quiz, "en")
        assert dto.description == ""


# ─────────────────────────────────────────────────────────────────────────────
# QuizService
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def quiz_service(mock_uow):
    loc_service = QuizLocalizationService()
    return QuizService(uow=mock_uow, localization_service=loc_service)


class TestGetCatalogue:
    @pytest.mark.asyncio
    async def test_returns_paginated_dto(self, quiz_service, mock_uow):
        mock_uow.quizzes.count_active.return_value = 2
        mock_uow.quizzes.get_all_active.return_value = [
            make_quiz(), make_quiz()
        ]
        result = await quiz_service.get_catalogue(locale="en", limit=10, offset=0)
        assert result.total == 2
        assert len(result.items) == 2
        assert result.page == 1

    @pytest.mark.asyncio
    async def test_empty_catalogue(self, quiz_service, mock_uow):
        mock_uow.quizzes.count_active.return_value = 0
        mock_uow.quizzes.get_all_active.return_value = []
        result = await quiz_service.get_catalogue(locale="en")
        assert result.total == 0
        assert result.items == []


class TestGetQuizForAttempt:
    @pytest.mark.asyncio
    async def test_not_found_raises(self, quiz_service, mock_uow):
        mock_uow.quizzes.get_by_id.return_value = None
        with pytest.raises(NotFoundException):
            await quiz_service.get_quiz_for_attempt(uuid.uuid4(), "en")

    @pytest.mark.asyncio
    async def test_inactive_quiz_raises(self, quiz_service, mock_uow):
        mock_uow.quizzes.get_by_id.return_value = make_quiz(is_active=False)
        with pytest.raises(NotFoundException):
            await quiz_service.get_quiz_for_attempt(uuid.uuid4(), "en")

    @pytest.mark.asyncio
    async def test_active_quiz_returns_dto(self, quiz_service, mock_uow):
        quiz = make_quiz(is_active=True)
        mock_uow.quizzes.get_by_id.return_value = quiz
        result = await quiz_service.get_quiz_for_attempt(quiz.id, "en")
        assert result.id == str(quiz.id)


class TestCreateQuiz:
    @pytest.mark.asyncio
    async def test_returns_new_uuid(self, quiz_service, mock_uow):
        dto = CreateQuizDTO(title={"en": "New Quiz"}, questions=[])
        result = await quiz_service.create_quiz(dto)
        assert isinstance(result, uuid.UUID)
        mock_uow.quizzes.add.assert_called_once()
        mock_uow.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_creates_with_questions(self, quiz_service, mock_uow):
        dto = CreateQuizDTO(
            title={"en": "Quiz"},
            questions=[
                CreateQuestionDTO(
                    type="single_choice",
                    text={"en": "Q"},
                    payload={"correct_id": "x", "options": []},
                )
            ],
        )
        await quiz_service.create_quiz(dto)
        mock_uow.questions.add.assert_called_once()


class TestSetQuizActiveStatus:
    @pytest.mark.asyncio
    async def test_not_found_raises(self, quiz_service, mock_uow):
        mock_uow.quizzes.set_active_status.return_value = False
        with pytest.raises(NotFoundException):
            await quiz_service.set_quiz_active_status(uuid.uuid4(), True)

    @pytest.mark.asyncio
    async def test_found_commits(self, quiz_service, mock_uow):
        mock_uow.quizzes.set_active_status.return_value = True
        await quiz_service.set_quiz_active_status(uuid.uuid4(), False)
        mock_uow.commit.assert_called_once()


class TestAppendQuestion:
    @pytest.mark.asyncio
    async def test_quiz_not_found_raises(self, quiz_service, mock_uow):
        mock_uow.quizzes.get_by_id.return_value = None
        dto = CreateQuestionDTO(
            type="fill_gap", text={"en": "Q"}, payload={"correct_answers": ["x"]}
        )
        with pytest.raises(NotFoundException):
            await quiz_service.append_question(uuid.uuid4(), dto)

    @pytest.mark.asyncio
    async def test_order_index_is_next_after_existing(self, quiz_service, mock_uow):
        q1 = make_question()
        q2 = make_question()
        quiz = make_quiz(questions=[q1, q2])
        mock_uow.quizzes.get_by_id.return_value = quiz
        captured = {}

        async def capture(entity, quiz_id):
            captured["entity"] = entity

        mock_uow.questions.add.side_effect = capture
        dto = CreateQuestionDTO(type="fill_gap", text={"en": "Q"}, payload={})
        await quiz_service.append_question(quiz.id, dto)

        assert captured["entity"].order_index == 2  # 3rd question


class TestDeleteQuestion:
    @pytest.mark.asyncio
    async def test_not_found_raises(self, quiz_service, mock_uow):
        mock_uow.questions.delete.return_value = False
        with pytest.raises(NotFoundException):
            await quiz_service.delete_question(uuid.uuid4())

    @pytest.mark.asyncio
    async def test_found_commits(self, quiz_service, mock_uow):
        mock_uow.questions.delete.return_value = True
        await quiz_service.delete_question(uuid.uuid4())
        mock_uow.commit.assert_called_once()