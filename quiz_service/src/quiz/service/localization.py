from __future__ import annotations

from typing import Any

from src.quiz.dto import QuestionDetailDTO, QuizDetailResponseDTO, QuizListItemDTO
from src.quiz.entities import QuestionEntity, QuizEntity
from src.quiz.enum import QuestionType


class QuizLocalizationService:
    """Domain service responsible for strictly localizing and sanitizing quiz entities.

    Enforces a strict whitelisting approach to payload transformation, guaranteeing
    that sensitive grading keys (e.g., correct answers) are never leaked to public DTOs.
    """

    def extract_text(self, text_map: dict[str, Any] | None, locale: str) -> str:
        """Extracts the most appropriate localized string from a mapped dictionary.

        Args:
            text_map: A dictionary containing localized strings keyed by language code.
            locale: The requested ISO language code.

        Returns:
            The localized string, falling back to English or the first available key,
            or an empty string if resolution fails.
        """
        if not text_map:
            return ""

        target_locale = locale.lower().strip()

        return str(
            text_map.get(target_locale)
            or text_map.get("en")
            or next(iter(text_map.values()), "")
        )

    def sanitize_question_payload(
            self, payload: dict[str, Any], question_type: QuestionType, locale: str
    ) -> dict[str, Any]:
        """Constructs a strictly sanitized, public-facing question payload.

        Args:
            payload: The raw, internal question configuration dictionary.
            question_type: The structural enum type of the question.
            locale: The requested ISO language code.

        Returns:
            A sanitized dictionary containing only display-safe attributes.
        """
        safe_payload: dict[str, Any] = {}

        if question_type in (QuestionType.SINGLE_CHOICE, QuestionType.MULTIPLE_CHOICE):
            safe_payload["options"] = [
                {
                    "id": str(opt.get("id", "")),
                    "text": self.extract_text(opt.get("text", {}), locale),
                }
                for opt in payload.get("options", [])
            ]

        elif question_type == QuestionType.MATCHING:
            safe_payload["pairs"] = [
                {
                    "pair_id": str(pair.get("pair_id", "")),
                    "left": self.extract_text(pair.get("left", {}), locale),
                    "right": self.extract_text(pair.get("right", {}), locale),
                }
                for pair in payload.get("pairs", [])
            ]

        elif question_type == QuestionType.FILL_GAP:
            pass

        return safe_payload

    def to_question_detail_dto(self, entity: QuestionEntity, locale: str) -> QuestionDetailDTO:
        """Transforms a domain question entity into a secure public presentation DTO.

        Args:
            entity: The internal QuestionEntity.
            locale: The requested ISO language code.

        Returns:
            A validated QuestionDetailDTO stripped of grading data.
        """
        return QuestionDetailDTO(
            id=str(entity.id),
            type=entity.type.value,
            order_index=entity.order_index,
            text=self.extract_text(entity.text, locale),
            payload=self.sanitize_question_payload(entity.payload, entity.type, locale),
        )

    def to_quiz_detail_dto(self, entity: QuizEntity, locale: str) -> QuizDetailResponseDTO:
        """Transforms a domain quiz entity and its nested questions into a public DTO.

        Args:
            entity: The internal QuizEntity.
            locale: The requested ISO language code.

        Returns:
            A validated QuizDetailResponseDTO.
        """
        return QuizDetailResponseDTO(
            id=str(entity.id),
            title=self.extract_text(entity.title, locale),
            description=self.extract_text(entity.description, locale),
            questions=[
                self.to_question_detail_dto(q, locale)
                for q in sorted(entity.questions, key=lambda x: x.order_index)
            ],
        )

    def to_quiz_list_item_dto(self, entity: QuizEntity, locale: str) -> QuizListItemDTO:
        """Transforms a domain quiz entity into a lightweight summary DTO for catalogue listings.

        Args:
            entity: The internal QuizEntity.
            locale: The requested ISO language code.

        Returns:
            A validated QuizListItemDTO containing basic metadata and pre-calculated counts.
        """
        return QuizListItemDTO(
            id=str(entity.id),
            title=self.extract_text(entity.title, locale),
            description=self.extract_text(entity.description, locale),
            question_count=entity.question_count,
        )