from __future__ import annotations

import uuid
from datetime import datetime, timezone

from src.uow import IUnitOfWork
from src.config.project import settings as project_settings
from src.attempt.entities import UserRewardedQuestionEntity, OutboxEventEntity
from shared.schemas import QuizRewardEvent, QuizRewardPayload
from shared.exceptions import InternalServerException


class RewardService:
    """Service for calculating idempotent quiz rewards and staging outbox events."""

    def __init__(self, uow: IUnitOfWork) -> None:
        """
        Initializes the service with a Unit of Work.

        Args:
            uow: Database Unit of Work instance.
        """
        self._uow = uow

    async def process_rewards(
        self,
        user_id: uuid.UUID,
        quiz_id: uuid.UUID,
        attempt_id: uuid.UUID,
        correct_question_ids: list[uuid.UUID],
    ) -> list[uuid.UUID]:
        """
        Calculates idempotent rewards and stages the outbox event in the current transaction.

        Args:
            user_id: ID of the user.
            quiz_id: ID of the quiz.
            attempt_id: ID of the attempt.
            correct_question_ids: List of correctly answered question IDs.

        Returns:
            List of newly rewarded question IDs.
        """
        if not correct_question_ids:
            return []

        already_rewarded_ids = await self._uow.user_rewards.get_rewarded_ids_by_questions(
            user_id, correct_question_ids
        )

        newly_rewarded_ids = [
            qid for qid in correct_question_ids if qid not in already_rewarded_ids
        ]

        if not newly_rewarded_ids:
            return []

        now = datetime.now(tz=timezone.utc)
        reward_entities = [
            UserRewardedQuestionEntity(
                user_id=user_id,
                question_id=qid,
                quiz_id=quiz_id,
                rewarded_at=now,
            )
            for qid in newly_rewarded_ids
        ]
        await self._uow.user_rewards.bulk_add(reward_entities)

        coins = len(newly_rewarded_ids) * project_settings.quiz_coins_per_correct_answer

        event_payload = QuizRewardEvent(
            payload=QuizRewardPayload(
                user_id=user_id,
                quiz_id=quiz_id,
                attempt_id=attempt_id,
                newly_rewarded_question_ids=newly_rewarded_ids,
                coins_to_award=coins,
            )
        )

        outbox_entity = OutboxEventEntity(
            id=uuid.uuid4(),
            event_type="quiz.rewarded",
            routing_key="finance.reward",
            payload=event_payload.model_dump(mode="json"),
            created_at=now,
            published_at=None,
            attempts=0,
        )
        await self._uow.outbox.add(outbox_entity)

        return newly_rewarded_ids