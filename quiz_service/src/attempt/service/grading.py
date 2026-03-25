from __future__ import annotations

from typing import Any

from src.quiz.entities import QuestionEntity


class GradingService:
    """Business logic for grading different types of quiz questions.
    
    Supports single choice, multiple choice, fill in the gap, and matching.
    """

    def check_answer(self, question: QuestionEntity, user_payload: Any) -> bool:
        """Grades a user's answer against the question's correct answer.

        Args:
            question: The question entity containing the correct answer payload.
            user_payload: The user's submitted answer payload.

        Returns:
            bool: True if the answer is correct, False otherwise.
        """
        q_type = question.type
        payload = question.payload

        if q_type == "single_choice":
            return str(user_payload.get("selected_id")) == str(payload.get("correct_id"))

        if q_type == "multiple_choice":
            user_ids = set(map(str, user_payload.get("selected_ids", [])))
            correct_ids = set(map(str, payload.get("correct_ids", [])))
            return user_ids == correct_ids

        if q_type == "fill_gap":
            user_text = str(user_payload.get("text", "")).strip().lower()
            correct_texts = [str(t).strip().lower() for t in payload.get("correct_answers", [])]
            return user_text in correct_texts

        if q_type == "matching":
            return self._check_matching(payload, user_payload)

        return False

    def _check_matching(self, payload: dict[str, Any], answer: dict[str, Any]) -> bool:
        """Verifies matched pairs for matching questions.

        Args:
            payload: Question payload containing correct pairs.
            answer: User submitted pairs.

        Returns:
            bool: True if all pairs match correctly.
        """
        correct_pairs = payload.get("pairs", [])
        user_pairs = answer.get("pairs", [])

        if len(correct_pairs) != len(user_pairs):
            return False

        correct_map = {str(p["left_id"]): str(p["right_id"]) for p in correct_pairs}
        
        for up in user_pairs:
            left = str(up.get("left_id"))
            right = str(up.get("right_id"))
            if correct_map.get(left) != right:
                return False
        
        return True
