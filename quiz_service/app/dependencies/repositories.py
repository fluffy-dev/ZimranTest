"""
Repository dependency type aliases.
Pure Annotated types via __init__ introspection.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.repositories.attempt_repository import AttemptRepository
from app.repositories.outbox_repository import OutboxRepository
from app.repositories.quiz_repository import QuizRepository
from app.services.grading_service import GradingService


# ── Annotated aliases ─────────────────────────────────────────────────────────

IQuizRepository    = Annotated[QuizRepository,    Depends()]
IAttemptRepository = Annotated[AttemptRepository, Depends()]
IOutboxRepository  = Annotated[OutboxRepository,  Depends()]
IGradingService    = Annotated[GradingService,    Depends()]
