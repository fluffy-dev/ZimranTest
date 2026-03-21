from __future__ import annotations

from typing import Any

from app.db.models import Question, QuestionType
from shared.exceptions import ValidationException
from shared.logging import get_logger

logger = get_logger(__name__)

# -----------------------------------------------------------------------
# Answer payload shapes (for reference / documentation):
#
# single_choice:   {"selected_id": "a"}
# fill_gap:        {"answer": "bitcoin"}
# multiple_choice: {"selected_ids": ["a", "c"]}
# matching:        {"pairs": [{"pair_id": "p1", "right_id": "r2"}, ...]}
#                  where right_id maps to the right element of the pair
# -----------------------------------------------------------------------


class GradingService:
    """
    Stateless service for checking correctness of a single question answer.

    Each question type has its own isolated _check_* method.
    This makes it trivial to add new types or modify grading logic (e.g. Levenshtein)
    without touching the calling code.
    """

    def check_answer(self, question: Question, answer_payload: dict[str, Any]) -> bool:
        """
        Returns True if the answer_payload is correct for the given question.
        Raises ValidationException if the answer format is invalid.
        """
        q_type = question.type
        try:
            if q_type == QuestionType.SINGLE_CHOICE:
                return self._check_single_choice(question.payload, answer_payload)
            elif q_type == QuestionType.FILL_GAP:
                return self._check_fill_gap(question.payload, answer_payload)
            elif q_type == QuestionType.MULTIPLE_CHOICE:
                return self._check_multiple_choice(question.payload, answer_payload)
            elif q_type == QuestionType.MATCHING:
                return self._check_matching(question.payload, answer_payload)
            else:
                raise ValidationException(f"Unknown question type: {q_type}")
        except KeyError as exc:
            raise ValidationException(
                f"Invalid answer payload for question type '{q_type}': missing key {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Private graders
    # ------------------------------------------------------------------

    @staticmethod
    def _check_single_choice(
        payload: dict[str, Any], answer: dict[str, Any]
    ) -> bool:
        """User must select exactly the one correct option ID."""
        correct_id: str = payload["correct_id"]
        selected_id: str = answer["selected_id"]
        return selected_id == correct_id

    @staticmethod
    def _check_fill_gap(
        payload: dict[str, Any], answer: dict[str, Any]
    ) -> bool:
        """
        User provides a free-text answer. Graded against a list of accepted strings.
        Normalization: strip whitespace, lowercase.
        Levenshtein can be plugged in here later without changing calling code.
        """
        correct_answers: list[str] = [s.lower().strip() for s in payload["correct_answers"]]
        user_answer: str = answer["answer"].lower().strip()
        return user_answer in correct_answers

    @staticmethod
    def _check_multiple_choice(
        payload: dict[str, Any], answer: dict[str, Any]
    ) -> bool:
        """
        User must select ALL correct options and ONLY those options.
        Order does not matter.
        """
        correct_ids: set[str] = set(payload["correct_ids"])
        selected_ids: set[str] = set(answer["selected_ids"])
        return correct_ids == selected_ids

    @staticmethod
    def _check_matching(
        payload: dict[str, Any], answer: dict[str, Any]
    ) -> bool:
        """
        User must correctly match ALL pairs.
        payload["pairs"]: [{"id": "p1", "left": {...}, "right": {...}}]
        answer["pairs"]:  [{"pair_id": "p1", "matched_pair_id": "p2"}]
        Strategy: build correct mapping {pair_id -> pair_id (itself)} and compare.
        In matching, each left item must be matched to its own pair's right item.
        The answer encodes: for each left item (pair_id), which right item did the user pick.
        """
        # Build ground truth: pair_id -> pair_id (correct match is always self)
        correct_pairs: dict[str, str] = {p["id"]: p["id"] for p in payload["pairs"]}
        user_pairs: dict[str, str] = {
            p["pair_id"]: p["matched_pair_id"] for p in answer["pairs"]
        }
        return correct_pairs == user_pairs
