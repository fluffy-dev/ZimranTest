import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import selectinload

from src.config.database.session import ISession
from src.attempt.models.attempt import AttemptStatus, QuizAttempt, UserQuestionAnswer, UserRewardedQuestion
from src.attempt.entities import QuizAttemptEntity
from shared.logging import get_logger

logger = get_logger(__name__)


def _map_attempt_entity(attempt: QuizAttempt) -> QuizAttemptEntity:
    return QuizAttemptEntity(
        id=attempt.id,
        quiz_id=attempt.quiz_id,
        user_id=attempt.user_id,
        status=attempt.status,
        score=attempt.score,
        total_questions=attempt.total_questions,
        started_at=attempt.started_at,
        completed_at=attempt.completed_at,
    )


class AttemptRepository:
    """Data access layer for quiz attempts mapping models to domain entities."""

    def __init__(self, session: ISession) -> None:
        self._session = session

    async def create_attempt(self, quiz_id: uuid.UUID, user_id: uuid.UUID) -> QuizAttemptEntity:
        attempt = QuizAttempt(quiz_id=quiz_id, user_id=user_id)
        self._session.add(attempt)
        await self._session.flush()
        await self._session.refresh(attempt)
        logger.info("Quiz attempt created", attempt_id=str(attempt.id))
        return _map_attempt_entity(attempt)

    async def get_by_id(self, attempt_id: uuid.UUID) -> QuizAttemptEntity | None:
        result = await self._session.execute(
            select(QuizAttempt)
            .where(QuizAttempt.id == attempt_id)
            .options(selectinload(QuizAttempt.answers))
        )
        attempt = result.scalar_one_or_none()
        return _map_attempt_entity(attempt) if attempt else None

    async def bulk_save_answers(
        self, attempt_id: uuid.UUID, answers: list[tuple[uuid.UUID, dict, bool]]
    ) -> None:
        db_answers = [
            UserQuestionAnswer(
                attempt_id=attempt_id,
                question_id=qid,
                answer_payload=payload,
                is_correct=is_correct,
            )
            for qid, payload, is_correct in answers
        ]
        self._session.add_all(db_answers)
        await self._session.flush()

    async def complete_attempt(
        self, attempt_id: uuid.UUID, score: int, total: int
    ) -> QuizAttemptEntity:
        result = await self._session.execute(select(QuizAttempt).where(QuizAttempt.id == attempt_id))
        attempt = result.scalar_one()
        attempt.status = AttemptStatus.COMPLETED
        attempt.score = score
        attempt.total_questions = total
        attempt.completed_at = datetime.now(tz=timezone.utc)
        await self._session.flush()
        return _map_attempt_entity(attempt)

    async def get_already_rewarded_question_ids(
        self, user_id: uuid.UUID, question_ids: list[uuid.UUID]
    ) -> set[uuid.UUID]:
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
        if not question_ids:
            return
        stmt = pg_insert(UserRewardedQuestion).values(
            [{"user_id": user_id, "question_id": qid} for qid in question_ids]
        ).on_conflict_do_nothing()
        await self._session.execute(stmt)
