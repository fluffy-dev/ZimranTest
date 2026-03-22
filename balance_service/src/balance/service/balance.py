from __future__ import annotations

import uuid

from src.balance.dependencies.repository import IBalanceRepository
from src.balance.entities import BalanceEntity, BalanceTransactionEntity
from shared.logging import get_logger
from shared.schemas import QuizRewardEvent

logger = get_logger(__name__)


class BalanceService:
    """Business logic layer for managing user virtual coin balances.

    Orchestrates all balance operations — reads, initialisation, and
    event-driven credits — while remaining fully independent of HTTP,
    database, or messaging frameworks. All persistence is delegated to
    the injected :class:`~src.balance.repositories.balance.BalanceRepository`.

    Idempotency is enforced at the repository level, so all methods on this
    service are safe to call multiple times with the same arguments.
    """

    def __init__(self, repo: IBalanceRepository) -> None:
        """Initialise the service with a balance repository.

        Args:
            repo: A :class:`BalanceRepository` instance (or any compatible
                implementation) providing the persistence operations. Typically
                injected via FastAPI's dependency system.
        """
        self._repo = repo

    async def get_balance(self, user_id: uuid.UUID) -> BalanceEntity:
        """Return the current balance for a user, creating it if absent.

        If the user does not yet have a balance record (e.g. they have never
        received a quiz reward), an initial zero-value balance is created by
        calling ``upsert_credit`` with ``amount=0``.

        Args:
            user_id: UUID of the user whose balance to retrieve.

        Returns:
            The existing or newly-created :class:`BalanceEntity` for the user.
        """
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
        """Apply a quiz reward credit to the user's balance from a domain event.

        This is the primary entry-point for event-driven balance changes. The
        event's ``event_id`` is used directly as the idempotency key, so
        re-delivering the same RabbitMQ message will not result in a
        double-credit.

        Special cases:
            - If ``coins_to_award <= 0`` the credit step is skipped entirely
              and the user's current balance is returned unchanged.
            - If ``coins_to_award <= 0`` *and* the user has no existing balance
              record, a zero-value balance is synthesised and returned so that
              subsequent reads are consistent.

        Args:
            event: A validated :class:`QuizRewardEvent` consumed from the
                ``quiz.questions.rewarded`` RabbitMQ topic.

        Returns:
            The updated (or unchanged) :class:`BalanceEntity` after processing.
        """
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
        """Retrieve a page of the user's transaction history, newest first.

        Converts 1-based ``page`` / ``page_size`` pagination parameters into
        the ``limit`` / ``offset`` values expected by the repository.

        Args:
            user_id: UUID of the user whose transactions to retrieve.
            page: 1-based page number. Defaults to ``1``.
            page_size: Number of records per page (1–100). Defaults to ``50``.

        Returns:
            A list of :class:`BalanceTransactionEntity` objects for the
            requested page, ordered newest-first. Returns an empty list when
            the user has no transactions or the page is beyond the last record.
        """
        offset = (page - 1) * page_size
        return await self._repo.get_transactions(
            user_id=user_id, limit=page_size, offset=offset
        )
