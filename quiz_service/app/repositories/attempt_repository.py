from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.dependencies.common import ISession
from app.db.models import AttemptStatus, QuizAttempt, UserQuestionAnswer, UserRewardedQuestion
from shared.logging import get_logger

logger = get_logger(__name__)


class AttemptRepository:
    """Data access layer for quiz attempts and per-question answers."""

    def __init__(self, session: ISession) -> None:
        self._session = session

    async def create_attempt(self, quiz_id: uuid.UUID, user_id: uuid.UUID) -> QuizAttempt:
        attempt = QuizAttempt(quiz_id=quiz_id, user_id=user_id)
        self._session.add(attempt)
        await self._session.flush()
        await self._session.refresh(attempt)
        logger.info("Quiz attempt created", attempt_id=str(attempt.id))
        return attempt

    async def get_by_id(self, attempt_id: uuid.UUID) -> QuizAttempt | None:
        result = await self._session.execute(
            select(QuizAttempt)
            .where(QuizAttempt.id == attempt_id)
            .options(selectinload(QuizAttempt.answers))
        )
        return result.scalar_one_or_none()

    async def bulk_save_answers(
        self, answers: list[UserQuestionAnswer]
    ) -> None:
        self._session.add_all(answers)
        await self._session.flush()

    async def complete_attempt(
        self, attempt: QuizAttempt, score: int, total: int
    ) -> QuizAttempt:
        attempt.status = AttemptStatus.COMPLETED
        attempt.score = score
        attempt.total_questions = total
        attempt.completed_at = datetime.now(tz=timezone.utc)
        await self._session.flush()
        return attempt

    async def get_already_rewarded_question_ids(
        self, user_id: uuid.UUID, question_ids: list[uuid.UUID]
    ) -> set[uuid.UUID]:
        """Returns question IDs from the given list that the user was already rewarded for."""
        if not question_ids:
            return set()
        result = await self._session.execute(
            select(UserRewardedQuestion.question_id).where(
                UserRewardedQuestion.user_id == user_id,
                UserRewardedQuestion.question_id.in_(question_ids),
            )
        )
        return {row[0] for row in result.all()}

    async def bulk_insert_rewarded_questions(
        self, user_id: uuid.UUID, question_ids: list[uuid.UUID]
    ) -> None:
        """INSERT ... ON CONFLICT DO NOTHING — safe to call even if some already exist."""
        if not question_ids:
            return
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        stmt = pg_insert(UserRewardedQuestion).values(
            [{"user_id": user_id, "question_id": qid} for qid in question_ids]
        ).on_conflict_do_nothing()
        await self._session.execute(stmt)
