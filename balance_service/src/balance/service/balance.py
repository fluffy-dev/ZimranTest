from __future__ import annotations

import uuid

from src.uow import IUnitOfWork
from src.balance.entities import BalanceEntity, BalanceTransactionEntity
from shared.logging import get_logger
from shared.schemas import QuizRewardEvent

logger = get_logger(__name__)


class BalanceService:
    """Business logic layer for managing user virtual coin balances.

    Orchestrates all balance operations — reads, initialisation, and
    event-driven credits — while remaining fully independent of HTTP,
    database, or messaging frameworks. All persistence is delegated to
    the Unit of Work which provides transactional repositories.
    """

    def __init__(self, uow: IUnitOfWork) -> None:
        """Initialise the service with a Unit of Work.

        Args:
            uow: A Unit of Work instance providing transactional access
                to the balance repository.
        """
        self._uow = uow

    async def get_balance(self, user_id: uuid.UUID) -> BalanceEntity:
        """Return the current balance for a user, creating it if absent.

        If the user does not yet have a balance record, an initial
        zero-value balance is created atomically.

        Args:
            user_id: UUID of the user whose balance to retrieve.

        Returns:
            The existing or newly-created BalanceEntity for the user.
        """
        async with self._uow:
            balance = await self._uow.balances.get_by_user_id(user_id)
            if balance is None:
                balance = await self._uow.balances.upsert_credit(
                    user_id=user_id,
                    amount=0,
                    idempotency_key=uuid.uuid4(),
                    description="Initial balance setup",
                )
                await self._uow.commit()
            return balance

    async def credit_from_quiz_event(
        self, event: QuizRewardEvent
    ) -> BalanceEntity:
        """Apply a quiz reward credit to the user's balance from a domain event.

        Uses the Unit of Work for atomic transaction management.
        The event's ``event_id`` is used directly as the idempotency key.

        Args:
            event: A validated QuizRewardEvent consumed from RabbitMQ.

        Returns:
            The updated (or unchanged) BalanceEntity after processing.
        """
        async with self._uow:
            if event.payload.coins_to_award <= 0:
                logger.info(
                    "Quiz event with 0 coins — skipping",
                    event_id=str(event.event_id),
                    user_id=str(event.payload.user_id),
                )
                balance = await self._uow.balances.get_by_user_id(event.payload.user_id)
                if balance is None:
                    balance = await self._uow.balances.upsert_credit(
                        user_id=event.payload.user_id,
                        amount=0,
                        idempotency_key=uuid.uuid4(),
                        description="Zero Credit event creation",
                    )
                    await self._uow.commit()
                return balance

            balance = await self._uow.balances.upsert_credit(
                user_id=event.payload.user_id,
                amount=event.payload.coins_to_award,
                idempotency_key=event.event_id,
                description=f"Quiz reward: attempt {event.payload.attempt_id}",
            )
            await self._uow.commit()

        return balance

    async def get_transactions(
        self, user_id: uuid.UUID, page: int = 1, page_size: int = 50
    ) -> list[BalanceTransactionEntity]:
        """Retrieve a page of the user's transaction history, newest first.

        Args:
            user_id: UUID of the user whose transactions to retrieve.
            page: 1-based page number. Defaults to 1.
            page_size: Number of records per page. Defaults to 50.

        Returns:
            A list of BalanceTransactionEntity objects for the requested page.
        """
        async with self._uow:
            offset = (page - 1) * page_size
            return await self._uow.balances.get_transactions(
                user_id=user_id, limit=page_size, offset=offset
            )
