from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.quiz.service.quiz import QuizService
from shared.exceptions import NotFoundException


def make_quiz_entity(
    quiz_id: uuid.UUID | None = None,
    title: dict | None = None,
    description: dict | None = None,
    is_active: bool = True,
    questions: list | None = None,
) -> SimpleNamespace:
    """Creates a lightweight QuizEntity-like object."""
    return SimpleNamespace(
        id=quiz_id or uuid.uuid4(),
        title=title or {"en": "English Title", "de": "Deutscher Titel"},
        description=description or {"en": "Description", "de": "Beschreibung"},
        is_active=is_active,
        questions=questions or [],
    )


def make_question_entity(
    q_id: uuid.UUID | None = None,
    q_type: str = "single_choice",
    order_index: int = 0,
    text: dict | None = None,
    payload: dict | None = None,
) -> SimpleNamespace:
    """Creates a lightweight QuestionEntity-like object."""
    return SimpleNamespace(
        id=q_id or uuid.uuid4(),
        type=q_type,
        order_index=order_index,
        text=text or {"en": "Question?", "de": "Frage?"},
        payload=payload or {"options": [{"id": "a", "text": {"en": "A"}}, {"id": "b", "text": {"en": "B"}}], "correct_id": "a"},
    )


@pytest.fixture
def mock_repo():
    return AsyncMock()


@pytest.fixture
def mock_redis():
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.setex = AsyncMock()
    r.scan_iter = MagicMock(return_value=AsyncIterHelper([]))
    r.delete = AsyncMock()
    return r


@pytest.fixture
def mock_uow(mock_repo):
    uow = AsyncMock()
    uow.quizzes = mock_repo
    uow.commit = AsyncMock()
    uow.rollback = AsyncMock()
    uow.__aenter__.return_value = uow
    uow.__aexit__.return_value = None
    return uow


class AsyncIterHelper:
    """Converts a list into an async iterator for mocking redis.scan_iter."""

    def __init__(self, items: list):
        self._items = items

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._items:
            raise StopAsyncIteration
        return self._items.pop(0)


@pytest.fixture
def service(mock_repo, mock_redis, mock_uow):
    return QuizService(quiz_repo=mock_repo, redis=mock_redis, uow=mock_uow)


class TestListQuizzes:
    async def test_cache_miss_hits_repo(self, service, mock_repo, mock_redis):
        """When cache is empty, repo is queried and result is cached."""
        quiz = make_quiz_entity(questions=[make_question_entity()])
        mock_repo.get_all_active.return_value = [quiz]
        mock_repo.count_active.return_value = 1

        result = await service.list_quizzes(locale="en", page=1, page_size=20)

        assert result.total == 1
        assert len(result.items) == 1
        assert result.items[0].title == "English Title"
        mock_repo.get_all_active.assert_awaited_once()
        mock_redis.setex.assert_awaited_once()

    async def test_cache_hit_skips_repo(self, service, mock_repo, mock_redis):
        """When cache contains data, repo is not queried."""
        cached_json = '{"items": [{"id": "abc", "title": "Cached", "description": null, "question_count": 0}], "total": 1, "page": 1, "page_size": 20}'
        mock_redis.get.return_value = cached_json

        result = await service.list_quizzes(locale="en")

        assert result.items[0].title == "Cached"
        mock_repo.get_all_active.assert_not_awaited()

    async def test_pagination_offset_calculation(self, service, mock_repo, mock_redis):
        """Page 3 with page_size 10 should call repo with offset=20."""
        mock_repo.get_all_active.return_value = []
        mock_repo.count_active.return_value = 0

        await service.list_quizzes(locale="en", page=3, page_size=10)

        mock_repo.get_all_active.assert_awaited_once_with(limit=10, offset=20)


class TestGetQuiz:
    async def test_not_found_raises(self, service, mock_repo, mock_redis):
        """Returns NotFoundException when quiz does not exist."""
        mock_repo.get_by_id.return_value = None

        with pytest.raises(NotFoundException):
            await service.get_quiz(quiz_id=uuid.uuid4(), locale="en")

    async def test_inactive_quiz_raises(self, service, mock_repo, mock_redis):
        """Returns NotFoundException when quiz is inactive."""
        mock_repo.get_by_id.return_value = make_quiz_entity(is_active=False)

        with pytest.raises(NotFoundException):
            await service.get_quiz(quiz_id=uuid.uuid4(), locale="en")

    async def test_localizes_title_and_description(self, service, mock_repo, mock_redis):
        """Verifies title/description are localized to the requested language."""
        quiz = make_quiz_entity(
            title={"en": "English", "de": "Deutsch"},
            description={"en": "Eng Desc", "de": "Deu Desc"},
            questions=[make_question_entity()],
        )
        mock_repo.get_by_id.return_value = quiz

        result = await service.get_quiz(quiz_id=quiz.id, locale="de")

        assert result.title == "Deutsch"
        assert result.description == "Deu Desc"

    async def test_locale_fallback_to_en(self, service, mock_repo, mock_redis):
        """Falls back to 'en' when requested locale is not available."""
        quiz = make_quiz_entity(
            title={"en": "English Only"},
            questions=[make_question_entity()],
        )
        mock_repo.get_by_id.return_value = quiz

        result = await service.get_quiz(quiz_id=quiz.id, locale="tr")

        assert result.title == "English Only"

    async def test_strips_correct_id_from_single_choice(self, service, mock_repo, mock_redis):
        """Correct answer key is removed from single_choice payload in response."""
        q = make_question_entity(
            q_type="single_choice",
            payload={"options": [{"id": "a", "text": {"en": "A"}}], "correct_id": "a"},
        )
        quiz = make_quiz_entity(questions=[q])
        mock_repo.get_by_id.return_value = quiz

        result = await service.get_quiz(quiz_id=quiz.id, locale="en")

        assert "correct_id" not in result.questions[0].payload

    async def test_strips_correct_ids_from_multiple_choice(self, service, mock_repo, mock_redis):
        """Correct answer keys are removed from multiple_choice payload."""
        q = make_question_entity(
            q_type="multiple_choice",
            payload={"options": [{"id": "a", "text": {"en": "A"}}], "correct_ids": ["a"]},
        )
        quiz = make_quiz_entity(questions=[q])
        mock_repo.get_by_id.return_value = quiz

        result = await service.get_quiz(quiz_id=quiz.id, locale="en")

        assert "correct_ids" not in result.questions[0].payload

    async def test_strips_correct_answers_from_fill_gap(self, service, mock_repo, mock_redis):
        """Correct answers removed from fill_gap payload."""
        q = make_question_entity(
            q_type="fill_gap",
            payload={"correct_answers": ["bitcoin", "btc"]},
        )
        quiz = make_quiz_entity(questions=[q])
        mock_repo.get_by_id.return_value = quiz

        result = await service.get_quiz(quiz_id=quiz.id, locale="en")

        assert "correct_answers" not in result.questions[0].payload

    async def test_cache_is_set_on_miss(self, service, mock_repo, mock_redis):
        """Cache is populated when quiz is fetched from DB."""
        quiz = make_quiz_entity(questions=[make_question_entity()])
        mock_repo.get_by_id.return_value = quiz

        await service.get_quiz(quiz_id=quiz.id, locale="en")

        mock_redis.setex.assert_awaited_once()


class TestCreateQuiz:
    async def test_creates_quiz_with_questions(self, service, mock_repo, mock_redis, mock_uow):
        """Creates a quiz and returns the detail response."""
        from src.quiz.dto import CreateQuizDTO, CreateQuestionDTO

        quiz = make_quiz_entity(questions=[make_question_entity()])
        mock_repo.create.return_value = quiz
        mock_repo.add_question.return_value = make_question_entity()
        mock_repo.get_by_id.return_value = quiz
        mock_repo.count_active.return_value = 1

        request = CreateQuizDTO(
            title={"en": "Test"},
            questions=[
                CreateQuestionDTO(type="single_choice", text={"en": "Q?"}, payload={"correct_id": "a"}),
            ],
        )

        result = await service.create_quiz(request)

        mock_repo.create.assert_awaited_once()
        mock_repo.add_question.assert_awaited_once()
        mock_uow.commit.assert_awaited_once()

    async def test_invalidates_list_cache(self, service, mock_repo, mock_redis):
        """Creating a quiz invalidates the list cache keys."""
        from src.quiz.dto import CreateQuizDTO

        quiz = make_quiz_entity(questions=[])
        mock_repo.create.return_value = quiz
        mock_repo.get_by_id.return_value = quiz

        keys_to_delete = ["quizzes:list:en:1:20", "quizzes:list:de:1:20"]
        mock_redis.scan_iter = MagicMock(return_value=AsyncIterHelper(keys_to_delete.copy()))

        await service.create_quiz(CreateQuizDTO(title={"en": "Test"}))

        assert mock_redis.delete.await_count == 2
