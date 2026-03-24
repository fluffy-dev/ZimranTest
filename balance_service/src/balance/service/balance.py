from __future__ import annotations

import uuid

from src.uow import IUnitOfWork
from src.balance.dto import BalanceResponseDTO, TransactionListResponseDTO, TransactionResponseDTO
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

    def __init__(self, uow: IUnitOfWork) -> None:
        """Initialise the service with a unit of work.

        Args:
            uow: A :class:`IUnitOfWork` instance providing the repositories
                and transaction control.
        """
        self._uow = uow

    async def get_balance(self, user_id: uuid.UUID) -> BalanceResponseDTO:
        """Return the current balance for a user, creating it if absent.

        Args:
            user_id: UUID of the user whose balance to retrieve.

        Returns:
            The existing or newly-created :class:`BalanceResponseDTO` for the user.
        """
        balance = await self._uow.balances.get_by_user_id(user_id)
        if balance is None:
            await self._uow.balances._ensure_balance_row(user_id)
            await self._uow.commit()
            balance = await self._uow.balances.get_by_user_id(user_id)
        if balance is None:
            raise RuntimeError(f"Failed to ensure balance row for user {user_id}")
            
        return BalanceResponseDTO(
            user_id=balance.user_id,
            amount=balance.amount,
            updated_at=balance.updated_at,
        )

    async def credit_from_quiz_event(
        self, event: QuizRewardEvent
    ) -> BalanceResponseDTO:
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
            The updated (or unchanged) :class:`BalanceResponseDTO` after processing.
        """
        if event.payload.coins_to_award <= 0:
            logger.info(
                "Quiz event with 0 coins — skipping",
                event_id=str(event.event_id),
                user_id=str(event.payload.user_id),
            )
            balance = await self._uow.balances.get_by_user_id(event.payload.user_id)
            if balance is None:
                await self._uow.balances._ensure_balance_row(event.payload.user_id)
                await self._uow.commit()
                balance = await self._uow.balances.get_by_user_id(event.payload.user_id)
            if balance is None:
                raise RuntimeError(f"Failed to ensure balance row for user {event.payload.user_id}")
        else:
            balance = await self._uow.balances.upsert_credit(
                user_id=event.payload.user_id,
                amount=event.payload.coins_to_award,
                idempotency_key=event.event_id,
                description=f"Quiz reward: attempt {event.payload.attempt_id}",
            )
            await self._uow.commit()

        return BalanceResponseDTO(
            user_id=balance.user_id,
            amount=balance.amount,
            updated_at=balance.updated_at,
        )

    async def get_transactions(
        self, user_id: uuid.UUID, page: int = 1, page_size: int = 50
    ) -> TransactionListResponseDTO:
        """Retrieve a page of the user's transaction history with total count.

        Converts 1-based ``page`` / ``page_size`` pagination parameters into
        the ``limit`` / ``offset`` values expected by the repository.

        Args:
            user_id: UUID of the user whose transactions to retrieve.
            page: 1-based page number. Defaults to ``1``.
            page_size: Number of records per page (1–100). Defaults to ``50``.

        Returns:
            A tuple of (list of transactions, total count).
        """
        offset = (page - 1) * page_size
        items = await self._uow.balances.get_transactions(
            user_id=user_id, limit=page_size, offset=offset
        )
        total = await self._uow.balances.get_transaction_count(user_id)
        return TransactionListResponseDTO(
                items=[
                    TransactionResponseDTO(
                        id=t.id,
                        user_id=t.user_id,
                        type=t.type,
                        amount=t.amount,
                        description=t.description,
                        created_at=t.created_at,
                    )
                    for t in items
                ],
                page=page,
                page_size=page_size,
                total=total,
            )
