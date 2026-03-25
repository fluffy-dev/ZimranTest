from enum import Enum


class QuestionType(str, Enum):
    """Enumeration of supported evaluation structures for quiz questions."""

    SINGLE_CHOICE = "single_choice"
    FILL_GAP = "fill_gap"
    MULTIPLE_CHOICE = "multiple_choice"
    MATCHING = "matching"