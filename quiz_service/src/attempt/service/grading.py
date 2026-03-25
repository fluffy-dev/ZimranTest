from __future__ import annotations

from typing import Any

from src.quiz.entities import QuestionEntity
from src.attempt.dto import StrictAnswerPayload


class GradingService:
    """Business logic for evaluating strictly typed user answers."""

    def check_answer(self, question: QuestionEntity, answer: StrictAnswerPayload) -> bool:
        """
        Evaluates a user's validated answer payload against the correct question payload.

        Args:
            question: The domain entity of the question containing the correct answers.
            answer: The strictly validated Pydantic answer payload.

        Returns:
            True if the answer is correct, False otherwise.
        """
        payload = question.payload
        q_type = answer.question_type

        if q_type == "single_choice":
            return str(answer.selected_id) == str(payload.get("correct_id"))

        if q_type == "multiple_choice":
            user_ids = {str(uid) for uid in answer.selected_ids}
            correct_ids = {str(cid) for cid in payload.get("correct_ids", [])}
            return user_ids == correct_ids

        if q_type == "fill_gap":
            user_text = answer.answer.strip().lower()
            correct_texts = [str(t).strip().lower() for t in payload.get("correct_answers", [])]
            return user_text in correct_texts

        if q_type == "matching":
            return self._check_matching(payload, answer)

        return False

    def _check_matching(self, payload: dict[str, Any], answer: StrictAnswerPayload) -> bool:
        """
        Verifies matched pairs for matching questions.

        Args:
            payload: Question payload containing correct pairs.
            answer: User submitted pairs strictly validated by Pydantic.

        Returns:
            True if all pairs match correctly.
        """
        correct_pairs = payload.get("pairs", [])
        user_pairs = answer.pairs

        if len(correct_pairs) != len(user_pairs):
            return False

        correct_map = {str(p.get("left_id")): str(p.get("right_id")) for p in correct_pairs}

        for up in user_pairs:
            left = str(up.pair_id)
            right = str(up.matched_pair_id)
            if correct_map.get(left) != right:
                return False

        return True