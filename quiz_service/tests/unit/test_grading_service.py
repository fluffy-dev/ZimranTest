from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.db.models import QuestionType
from app.services.grading_service import GradingService
from shared.exceptions import ValidationException


@pytest.fixture
def grading() -> GradingService:
    return GradingService()


def make_question(q_type: str, payload: dict) -> SimpleNamespace:
    """Creates a lightweight question-like object for unit testing without SQLAlchemy overhead."""
    return SimpleNamespace(type=q_type, payload=payload)


class TestSingleChoice:
    def test_correct_answer(self, grading):
        q = make_question(
            QuestionType.SINGLE_CHOICE,
            {"options": [{"id": "a"}, {"id": "b"}], "correct_id": "a"},
        )
        assert grading.check_answer(q, {"selected_id": "a"}) is True

    def test_wrong_answer(self, grading):
        q = make_question(
            QuestionType.SINGLE_CHOICE,
            {"options": [{"id": "a"}, {"id": "b"}], "correct_id": "a"},
        )
        assert grading.check_answer(q, {"selected_id": "b"}) is False

    def test_missing_key_raises(self, grading):
        q = make_question(QuestionType.SINGLE_CHOICE, {"correct_id": "a"})
        with pytest.raises(ValidationException):
            grading.check_answer(q, {"wrong_key": "a"})


class TestFillGap:
    def test_exact_match(self, grading):
        q = make_question(QuestionType.FILL_GAP, {"correct_answers": ["Bitcoin", "BTC"]})
        assert grading.check_answer(q, {"answer": "bitcoin"}) is True

    def test_case_insensitive(self, grading):
        q = make_question(QuestionType.FILL_GAP, {"correct_answers": ["HELLO"]})
        assert grading.check_answer(q, {"answer": "  hello  "}) is True

    def test_wrong_answer(self, grading):
        q = make_question(QuestionType.FILL_GAP, {"correct_answers": ["bitcoin"]})
        assert grading.check_answer(q, {"answer": "ethereum"}) is False

    def test_multiple_accepted_answers(self, grading):
        q = make_question(QuestionType.FILL_GAP, {"correct_answers": ["bitcoin", "btc", "xbt"]})
        assert grading.check_answer(q, {"answer": "xbt"}) is True


class TestMultipleChoice:
    def test_all_correct(self, grading):
        q = make_question(
            QuestionType.MULTIPLE_CHOICE,
            {"options": [{"id": "a"}, {"id": "b"}, {"id": "c"}], "correct_ids": ["a", "c"]},
        )
        assert grading.check_answer(q, {"selected_ids": ["c", "a"]}) is True

    def test_extra_selection_fails(self, grading):
        q = make_question(QuestionType.MULTIPLE_CHOICE, {"correct_ids": ["a", "c"]})
        assert grading.check_answer(q, {"selected_ids": ["a", "b", "c"]}) is False

    def test_partial_selection_fails(self, grading):
        q = make_question(QuestionType.MULTIPLE_CHOICE, {"correct_ids": ["a", "c"]})
        assert grading.check_answer(q, {"selected_ids": ["a"]}) is False


class TestMatching:
    def test_all_correct(self, grading):
        q = make_question(
            QuestionType.MATCHING,
            {"pairs": [{"id": "p1", "left": {}, "right": {}}, {"id": "p2", "left": {}, "right": {}}]},
        )
        answer = {"pairs": [{"pair_id": "p1", "matched_pair_id": "p1"}, {"pair_id": "p2", "matched_pair_id": "p2"}]}
        assert grading.check_answer(q, answer) is True

    def test_one_wrong_pair(self, grading):
        q = make_question(
            QuestionType.MATCHING,
            {"pairs": [{"id": "p1", "left": {}, "right": {}}, {"id": "p2", "left": {}, "right": {}}]},
        )
        answer = {"pairs": [{"pair_id": "p1", "matched_pair_id": "p2"}, {"pair_id": "p2", "matched_pair_id": "p1"}]}
        assert grading.check_answer(q, answer) is False

    def test_empty_pairs_correct(self, grading):
        q = make_question(QuestionType.MATCHING, {"pairs": []})
        assert grading.check_answer(q, {"pairs": []}) is True
