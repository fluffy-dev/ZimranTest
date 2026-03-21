from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Balance, BalanceTransaction
from app.dependencies.repositories import IBalanceRepository
    
from shared.logging import get_logger
from shared.schemas import QuizRewardEvent

logger = get_logger(__name__)


class BalanceService:
    """
    Manages user virtual currency.
    All operations go through the repository which enforces idempotency constraints.
    """

    def __init__(self, repo: IBalanceRepository) -> None:
        self._repo = repo

    async def get_balance(self, user_id: uuid.UUID) -> Balance:
        """Returns current balance; creates a zero balance record if user not found."""
        balance = await self._repo.get_by_user_id(user_id)
        if balance is None:
            # Upsert will lazily create if not exists
            balance = await self._repo.upsert_credit(
                user_id=user_id,
                amount=0,
                idempotency_key=uuid.uuid4(),
                description="Initial balance setup",
            )
        return balance

    async def credit_from_quiz_event(
        self, event: QuizRewardEvent
    ) -> Balance:
        """
        Credits user balance based on a quiz reward event.
        Uses event.event_id as idempotency_key — safe to call multiple times.
        """
        if event.payload.coins_to_award <= 0:
            logger.info(
                "Quiz event with 0 coins — skipping",
                event_id=str(event.event_id),
                user_id=str(event.payload.user_id),
            )
            # Return current balance without modification
            balance = await self._repo.get_by_user_id(event.payload.user_id)
            if balance is None:
                balance = Balance(user_id=event.payload.user_id, amount=0)
            return balance

        return await self._repo.upsert_credit(
            user_id=event.payload.user_id,
            amount=event.payload.coins_to_award,
            idempotency_key=event.event_id,
            description=f"Quiz reward: attempt {event.payload.attempt_id}",
        )

    async def get_transactions(
        self, user_id: uuid.UUID, page: int = 1, page_size: int = 50
    ) -> list[BalanceTransaction]:
        offset = (page - 1) * page_size
        return await self._repo.get_transactions(
            user_id=user_id, limit=page_size, offset=offset
        )
