from __future__ import annotations

import uuid

from src.uow import IUnitOfWork
from src.balance.dto import BalanceResponseDTO, TransactionListResponseDTO, TransactionResponseDTO
from shared.logging import get_logger
from shared.schemas import QuizRewardEvent
from shared.exceptions import IdempotencyMismatchError

logger = get_logger(__name__)


class BalanceService:
    """Business logic layer for orchestrating user virtual coin balances."""

    def __init__(self, uow: IUnitOfWork) -> None:
        """Initializes the service with a Unit of Work.

        Args:
            uow: The Unit of Work managing database transactions and repositories.
        """
        self._uow = uow

    async def get_balance(self, user_id: uuid.UUID) -> BalanceResponseDTO:
        """Retrieves the current balance for a user, lazily creating it if absent.

        Args:
            user_id: The UUID identifying the user.

        Returns:
            A populated BalanceResponseDTO.
        """
        async with self._uow:
            balance = await self._uow.balances.get_by_user_id(user_id)

            if not balance:
                balance = await self._uow.balances.upsert_amount(user_id, 0)
                await self._uow.commit()

            return BalanceResponseDTO(
                user_id=balance.user_id,
                amount=balance.amount,
                updated_at=balance.updated_at,
            )

    async def credit_from_quiz_event(self, event: QuizRewardEvent) -> BalanceResponseDTO:
        """Applies a quiz reward credit to the user's ledger from a domain event.

        Args:
            event: The validated QuizRewardEvent payload containing reward data.

        Returns:
            The newly updated BalanceResponseDTO.
        """
        if event.payload.coins_to_award <= 0:
            logger.info(
                "Skipping zero-value quiz reward event",
                event_id=str(event.event_id),
                user_id=str(event.payload.user_id),
            )
            return await self.get_balance(event.payload.user_id)

        async with self._uow:
            transaction = await self._uow.transactions.insert_idempotent(
                user_id=event.payload.user_id,
                amount=event.payload.coins_to_award,
                idempotency_key=event.event_id,
                description=f"Quiz reward: attempt {event.payload.attempt_id}",
            )

            if not transaction:
                return await self._resolve_duplicate_event(
                    user_id=event.payload.user_id,
                    event_id=event.event_id,
                    expected_amount=event.payload.coins_to_award,
                )

            balance = await self._uow.balances.upsert_amount(
                user_id=event.payload.user_id,
                amount=event.payload.coins_to_award,
            )
            await self._uow.commit()

            return BalanceResponseDTO(
                user_id=balance.user_id,
                amount=balance.amount,
                updated_at=balance.updated_at,
            )

    async def _resolve_duplicate_event(
            self, user_id: uuid.UUID, event_id: uuid.UUID, expected_amount: int
    ) -> BalanceResponseDTO:
        """Handles the fallback logic when an idempotency key collision occurs.

        Args:
            user_id: The UUID identifying the user.
            event_id: The upstream event UUID causing the collision.
            expected_amount: The coin amount expected by the current event payload.

        Returns:
            A BalanceResponseDTO representing the user's current safe state.

        Raises:
            IdempotencyMismatchError: If the collision involves mismatched amounts.
        """
        existing_txn = await self._uow.transactions.get_by_idempotency_key(event_id)

        if existing_txn and existing_txn.amount != expected_amount:
            logger.warning(
                "Idempotency mismatch detected",
                idempotency_key=str(event_id),
            )
            raise IdempotencyMismatchError(
                f"Idempotency key {event_id} already used with a different amount."
            )

        logger.info(
            "Duplicate idempotency key safely ignored",
            idempotency_key=str(event_id),
        )

        balance = await self._uow.balances.get_by_user_id(user_id)
        if not balance:
            balance = await self._uow.balances.upsert_amount(user_id, 0)
            await self._uow.commit()

        return BalanceResponseDTO(
            user_id=balance.user_id,
            amount=balance.amount,
            updated_at=balance.updated_at,
        )

    async def get_transactions(
            self, user_id: uuid.UUID, page: int = 1, page_size: int = 50
    ) -> TransactionListResponseDTO:
        """Retrieves a paginated list of the user's ledger history.

        Args:
            user_id: The UUID identifying the user.
            page: The 1-based page number to retrieve.
            page_size: The number of transactions per page.

        Returns:
            A TransactionListResponseDTO containing the paginated history.
        """
        offset = (page - 1) * page_size

        async with self._uow:
            items = await self._uow.transactions.get_paginated_by_user(
                user_id=user_id, limit=page_size, offset=offset
            )
            total = await self._uow.transactions.count_by_user(user_id)

            return TransactionListResponseDTO(
                items=[
                    TransactionResponseDTO(
                        id=t.id,
                        user_id=t.user_id,
                        type=t.type.value,
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