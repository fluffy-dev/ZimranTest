from __future__ import annotations

import uuid

from src.balance.dependencies.repository import IBalanceRepository
from src.balance.entities import BalanceEntity, BalanceTransactionEntity
from shared.logging import get_logger
from shared.schemas import QuizRewardEvent

logger = get_logger(__name__)


class BalanceService:
    """
    Manages user virtual currency fully isolated from implementation frameworks.
    All operations go through the repository which enforces idempotency constraints.
    """

    def __init__(self, repo: IBalanceRepository) -> None:
        self._repo = repo

    async def get_balance(self, user_id: uuid.UUID) -> BalanceEntity:
        balance = await self._repo.get_by_user_id(user_id)
        if balance is None:
            balance = await self._repo.upsert_credit(
                user_id=user_id,
                amount=0,
                idempotency_key=uuid.uuid4(),
                description="Initial balance setup",
            )
        return balance

    async def credit_from_quiz_event(
        self, event: QuizRewardEvent
    ) -> BalanceEntity:
        if event.payload.coins_to_award <= 0:
            logger.info(
                "Quiz event with 0 coins — skipping",
                event_id=str(event.event_id),
                user_id=str(event.payload.user_id),
            )
            balance = await self._repo.get_by_user_id(event.payload.user_id)
            if balance is None:
                # Re-check and build an entity mimicking exactly what the repo returned handling edge case
                balance = await self._repo.upsert_credit(
                    user_id=event.payload.user_id, amount=0, idempotency_key=uuid.uuid4(), description="Zero Credit event creation"
                )
            return balance

        return await self._repo.upsert_credit(
            user_id=event.payload.user_id,
            amount=event.payload.coins_to_award,
            idempotency_key=event.event_id,
            description=f"Quiz reward: attempt {event.payload.attempt_id}",
        )

    async def get_transactions(
        self, user_id: uuid.UUID, page: int = 1, page_size: int = 50
    ) -> list[BalanceTransactionEntity]:
        offset = (page - 1) * page_size
        return await self._repo.get_transactions(
            user_id=user_id, limit=page_size, offset=offset
        )
