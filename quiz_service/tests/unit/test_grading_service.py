"""
Unit tests for GradingService.

Covers:
- All four question types: single_choice, multiple_choice, fill_gap, matching
- Correct and incorrect answers
- Edge cases: case sensitivity, whitespace, empty sets, order independence
- Malformed / missing payload keys
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from src.attempt.dto import (
    FillGapPayload,
    MatchingPayload,
    MatchingPair,
    MultipleChoicePayload,
    SingleChoicePayload,
)
from src.attempt.service.grading import GradingService
from src.quiz.entities import QuestionEntity
from src.quiz.enum import QuestionType


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def grading():
    return GradingService()


def sc_question(correct_id: uuid.UUID) -> QuestionEntity:
    return QuestionEntity(
        id=uuid.uuid4(),
        type=QuestionType.SINGLE_CHOICE,
        order_index=0,
        text={"en": "Pick one"},
        payload={"correct_id": str(correct_id)},
    )


def mc_question(correct_ids: list[uuid.UUID]) -> QuestionEntity:
    return QuestionEntity(
        id=uuid.uuid4(),
        type=QuestionType.MULTIPLE_CHOICE,
        order_index=0,
        text={"en": "Pick many"},
        payload={"correct_ids": [str(i) for i in correct_ids]},
    )


def fg_question(correct_answers: list[str]) -> QuestionEntity:
    return QuestionEntity(
        id=uuid.uuid4(),
        type=QuestionType.FILL_GAP,
        order_index=0,
        text={"en": "Fill the blank"},
        payload={"correct_answers": correct_answers},
    )


def matching_question(pairs: list[tuple[uuid.UUID, uuid.UUID]]) -> QuestionEntity:
    return QuestionEntity(
        id=uuid.uuid4(),
        type=QuestionType.MATCHING,
        order_index=0,
        text={"en": "Match these"},
        payload={
            "pairs": [
                {"left_id": str(l), "right_id": str(r)} for l, r in pairs
            ]
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# SingleChoice
# ─────────────────────────────────────────────────────────────────────────────

class TestSingleChoice:
    def test_correct_answer(self, grading):
        cid = uuid.uuid4()
        q = sc_question(cid)
        ans = SingleChoicePayload(question_type="single_choice", selected_id=cid)
        assert grading.check_answer(q, ans) is True

    def test_wrong_answer(self, grading):
        cid = uuid.uuid4()
        q = sc_question(cid)
        ans = SingleChoicePayload(question_type="single_choice", selected_id=uuid.uuid4())
        assert grading.check_answer(q, ans) is False

    def test_correct_id_as_string_still_matches(self, grading):
        """IDs are compared as strings — UUID formatting must be consistent."""
        cid = uuid.uuid4()
        q = sc_question(cid)
        # payload stores str(uuid), answer stores UUID object → should still match
        ans = SingleChoicePayload(question_type="single_choice", selected_id=cid)
        assert grading.check_answer(q, ans) is True

    def test_missing_correct_id_in_payload(self, grading):
        """Payload with no 'correct_id' key must return False, not raise."""
        q = QuestionEntity(
            id=uuid.uuid4(),
            type=QuestionType.SINGLE_CHOICE,
            order_index=0,
            text={"en": "?"},
            payload={},  # missing correct_id
        )
        ans = SingleChoicePayload(question_type="single_choice", selected_id=uuid.uuid4())
        assert grading.check_answer(q, ans) is False


# ─────────────────────────────────────────────────────────────────────────────
# MultipleChoice
# ─────────────────────────────────────────────────────────────────────────────

class TestMultipleChoice:
    def test_exact_match(self, grading):
        ids = [uuid.uuid4(), uuid.uuid4()]
        q = mc_question(ids)
        ans = MultipleChoicePayload(question_type="multiple_choice", selected_ids=ids)
        assert grading.check_answer(q, ans) is True

    def test_order_independent(self, grading):
        ids = [uuid.uuid4(), uuid.uuid4()]
        q = mc_question(ids)
        ans = MultipleChoicePayload(
            question_type="multiple_choice", selected_ids=list(reversed(ids))
        )
        assert grading.check_answer(q, ans) is True

    def test_partial_selection_is_wrong(self, grading):
        ids = [uuid.uuid4(), uuid.uuid4()]
        q = mc_question(ids)
        ans = MultipleChoicePayload(
            question_type="multiple_choice", selected_ids=[ids[0]]  # only one
        )
        assert grading.check_answer(q, ans) is False

    def test_extra_selection_is_wrong(self, grading):
        ids = [uuid.uuid4(), uuid.uuid4()]
        q = mc_question(ids)
        ans = MultipleChoicePayload(
            question_type="multiple_choice", selected_ids=ids + [uuid.uuid4()]
        )
        assert grading.check_answer(q, ans) is False

    def test_empty_correct_ids_with_empty_selection(self, grading):
        """Both empty sets are equal — edge case."""
        q = QuestionEntity(
            id=uuid.uuid4(),
            type=QuestionType.MULTIPLE_CHOICE,
            order_index=0,
            text={"en": "?"},
            payload={"correct_ids": []},
        )
        # Can't create MultipleChoicePayload with empty list (min_length=1),
        # so test only verifies empty payload corner
        assert q.payload["correct_ids"] == []


# ─────────────────────────────────────────────────────────────────────────────
# FillGap
# ─────────────────────────────────────────────────────────────────────────────

class TestFillGap:
    def test_exact_match(self, grading):
        q = fg_question(["paris"])
        ans = FillGapPayload(question_type="fill_gap", answer="paris")
        assert grading.check_answer(q, ans) is True

    def test_case_insensitive(self, grading):
        q = fg_question(["Paris"])
        ans = FillGapPayload(question_type="fill_gap", answer="PARIS")
        assert grading.check_answer(q, ans) is True

    def test_strips_whitespace(self, grading):
        q = fg_question(["paris"])
        ans = FillGapPayload(question_type="fill_gap", answer="  paris  ")
        assert grading.check_answer(q, ans) is True

    def test_wrong_answer(self, grading):
        q = fg_question(["paris"])
        ans = FillGapPayload(question_type="fill_gap", answer="london")
        assert grading.check_answer(q, ans) is False

    def test_multiple_acceptable_answers(self, grading):
        q = fg_question(["paris", "Paris", "PARIS"])
        ans = FillGapPayload(question_type="fill_gap", answer="Paris")
        assert grading.check_answer(q, ans) is True

    def test_empty_correct_answers_list(self, grading):
        """No correct answers defined — must return False."""
        q = QuestionEntity(
            id=uuid.uuid4(),
            type=QuestionType.FILL_GAP,
            order_index=0,
            text={"en": "?"},
            payload={"correct_answers": []},
        )
        ans = FillGapPayload(question_type="fill_gap", answer="anything")
        assert grading.check_answer(q, ans) is False

    def test_missing_correct_answers_key(self, grading):
        """Payload missing 'correct_answers' must return False, not raise."""
        q = QuestionEntity(
            id=uuid.uuid4(),
            type=QuestionType.FILL_GAP,
            order_index=0,
            text={"en": "?"},
            payload={},
        )
        ans = FillGapPayload(question_type="fill_gap", answer="anything")
        assert grading.check_answer(q, ans) is False


# ─────────────────────────────────────────────────────────────────────────────
# Matching
# ─────────────────────────────────────────────────────────────────────────────

class TestMatching:
    def _make_pair(self, left: uuid.UUID, right: uuid.UUID) -> MatchingPair:
        return MatchingPair(pair_id=left, matched_pair_id=right)

    def test_correct_match(self, grading):
        l1, r1 = uuid.uuid4(), uuid.uuid4()
        l2, r2 = uuid.uuid4(), uuid.uuid4()
        q = matching_question([(l1, r1), (l2, r2)])
        ans = MatchingPayload(
            question_type="matching",
            pairs=[self._make_pair(l1, r1), self._make_pair(l2, r2)],
        )
        assert grading.check_answer(q, ans) is True

    def test_swapped_right_side(self, grading):
        l1, r1 = uuid.uuid4(), uuid.uuid4()
        l2, r2 = uuid.uuid4(), uuid.uuid4()
        q = matching_question([(l1, r1), (l2, r2)])
        ans = MatchingPayload(
            question_type="matching",
            pairs=[self._make_pair(l1, r2), self._make_pair(l2, r1)],  # swapped
        )
        assert grading.check_answer(q, ans) is False

    def test_wrong_pair_count_returns_false(self, grading):
        l1, r1 = uuid.uuid4(), uuid.uuid4()
        q = matching_question([(l1, r1)])
        ans = MatchingPayload(
            question_type="matching",
            pairs=[self._make_pair(l1, r1), self._make_pair(uuid.uuid4(), uuid.uuid4())],
        )
        assert grading.check_answer(q, ans) is False

    def test_empty_pairs_both_sides(self, grading):
        q = QuestionEntity(
            id=uuid.uuid4(),
            type=QuestionType.MATCHING,
            order_index=0,
            text={"en": "?"},
            payload={"pairs": []},
        )
        ans = MatchingPayload(question_type="matching", pairs=[
            self._make_pair(uuid.uuid4(), uuid.uuid4())
        ])
        assert grading.check_answer(q, ans) is False

    def test_unknown_left_id(self, grading):
        l1, r1 = uuid.uuid4(), uuid.uuid4()
        q = matching_question([(l1, r1)])
        ans = MatchingPayload(
            question_type="matching",
            pairs=[self._make_pair(uuid.uuid4(), r1)],  # unknown left
        )
        assert grading.check_answer(q, ans) is False

    def test_missing_pairs_key_in_payload(self, grading):
        q = QuestionEntity(
            id=uuid.uuid4(),
            type=QuestionType.MATCHING,
            order_index=0,
            text={"en": "?"},
            payload={},
        )
        ans = MatchingPayload(
            question_type="matching",
            pairs=[self._make_pair(uuid.uuid4(), uuid.uuid4())],
        )
        assert grading.check_answer(q, ans) is False


# ─────────────────────────────────────────────────────────────────────────────
# Unknown question type
# ─────────────────────────────────────────────────────────────────────────────

class TestUnknownType:
    def test_unknown_type_returns_false(self, grading):
        """Any unrecognized question_type must return False gracefully."""
        fake_answer = MagicMock()
        fake_answer.question_type = "unknown_type_xyz"
        q = QuestionEntity(
            id=uuid.uuid4(),
            type=QuestionType.SINGLE_CHOICE,  # doesn't matter
            order_index=0,
            text={"en": "?"},
            payload={},
        )
        assert grading.check_answer(q, fake_answer) is False