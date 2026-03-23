import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import selectinload

from src.attempt.enum import AttemptStatusEnum
from src.config.database.session import ISession
from src.attempt.models.attempt import QuizAttempt, UserQuestionAnswer, UserRewardedQuestion
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
    """
    Data access layer for quiz attempts, mapping database models to domain entities.
    Handles storage and retrieval of attempts, user answers, and rewards.
    """

    def __init__(self, session: ISession) -> None:
        """Initializes the repository with a database session."""
        self._session = session

    async def create_attempt(self, quiz_id: uuid.UUID, user_id: uuid.UUID) -> QuizAttemptEntity:
        """
        Creates a new quiz attempt record in the database.

        Args:
            quiz_id: The unique identifier of the quiz.
            user_id: The unique identifier of the user.

        Returns:
            QuizAttemptEntity: The newly created attempt as a domain entity.
        """
        attempt = QuizAttempt(quiz_id=quiz_id, user_id=user_id)
        self._session.add(attempt)
        await self._session.flush()
        await self._session.refresh(attempt)
        logger.info("Quiz attempt created", attempt_id=str(attempt.id))
        return _map_attempt_entity(attempt)

    async def get_by_id(self, attempt_id: uuid.UUID) -> QuizAttemptEntity | None:
        """
        Retrieves a quiz attempt by its unique identifier.
        Eagerly loads related answers.

        Args:
            attempt_id: The unique identifier of the attempt.

        Returns:
            QuizAttemptEntity | None: The found attempt or None if it doesn't exist.
        """
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
        """
        Saves multiple user answers associated with a specific attempt.

        Args:
            attempt_id: The unique identifier of the attempt.
            answers: List of tuples containing (question_id, answer_payload, is_correct).
        """
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
        """
        Updates an attempt's status to COMPLETED and records the final score.

        Args:
            attempt_id: The unique identifier of the attempt.
            score: The number of correct answers.
            total: The total number of questions answered.

        Returns:
            QuizAttemptEntity: The updated attempt domain entity.
        """
        result = await self._session.execute(select(QuizAttempt).where(QuizAttempt.id == attempt_id))
        attempt = result.scalar_one()
        attempt.status = AttemptStatusEnum.COMPLETED
        attempt.score = score
        attempt.total_questions = total
        attempt.completed_at = datetime.now(tz=timezone.utc)
        await self._session.flush()
        return _map_attempt_entity(attempt)

    async def get_already_rewarded_question_ids(
        self, user_id: uuid.UUID, question_ids: list[uuid.UUID]
    ) -> set[uuid.UUID]:
        """
        Identifies which of the given question IDs have already been rewarded for the user.

        Args:
            user_id: The unique identifier of the user.
            question_ids: A list of question IDs to check for existing rewards.

        Returns:
            set[uuid.UUID]: A set of question IDs that were already rewarded.
        """
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
        """
        Atomically records new rewarded questions for a user using an upsert-like operation.

        Args:
            user_id: The unique identifier of the user.
            question_ids: A list of question IDs to mark as rewarded.
        """
        if not question_ids:
            return
        stmt = pg_insert(UserRewardedQuestion).values(
            [{"user_id": user_id, "question_id": qid} for qid in question_ids]
        ).on_conflict_do_nothing()
        await self._session.execute(stmt)
