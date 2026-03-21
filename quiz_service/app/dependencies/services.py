"""
Service dependency type aliases.
Pure Annotated types via __init__ introspection.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.services.attempt_service import AttemptService
from app.services.quiz_service import QuizService


# ── Annotated aliases ─────────────────────────────────────────────────────────

IQuizService    = Annotated[QuizService,    Depends()]
IAttemptService = Annotated[AttemptService, Depends()]
