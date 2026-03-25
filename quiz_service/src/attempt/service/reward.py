from __future__ import annotations

import uuid
from typing import Any

from src.uow import IUnitOfWork
from src.config.project import settings as project_settings
from shared.logging import get_logger
from shared.schemas import QuizRewardEvent, QuizRewardPayload

logger = get_logger(__name__)


class RewardService:
    """Service for processing quiz rewards and publishing events.
    
    Encapsulates the business logic for calculating coins and marking questions as rewarded.
    """

    def __init__(self, uow: IUnitOfWork) -> None:
        """Initializes the service with a Unit of Work.

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
        """Calculates rewards for correct answers and records them.

        Args:
            user_id: ID of the user.
            quiz_id: ID of the quiz.
            attempt_id: ID of the attempt.
            correct_question_ids: List of question IDs that were answered correctly.

        Returns:
            list[uuid.UUID]: List of question IDs that were newly rewarded.
        """
        rewarded_ids = await self._uow.attempts.get_rewarded_question_ids(user_id, quiz_id)
        newly_rewarded_ids = [qid for qid in correct_question_ids if qid not in rewarded_ids]

        if not newly_rewarded_ids:
            return []

        await self._uow.attempts.record_rewards(user_id, quiz_id, newly_rewarded_ids)

        coins = len(newly_rewarded_ids) * project_settings.quiz_coins_per_correct_answer
        
        event = QuizRewardEvent(
            payload=QuizRewardPayload(
                    user_id=user_id,
                    quiz_id=quiz_id,
                    attempt_id=attempt_id,
                    newly_rewarded_question_ids=newly_rewarded_ids,
                    coins_to_award=coins
                )
            )
        
        await self._uow.outbox.save_event(
            event_type="quiz.rewarded",
            routing_key="finance.reward",
            payload=event.model_dump(),
        )

        return newly_rewarded_ids
