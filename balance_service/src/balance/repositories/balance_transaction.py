from __future__ import annotations

import uuid

from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from sqlalchemy.ext.asyncio import AsyncSession
from src.balance.models.balance_transaction import BalanceTransaction
from src.balance.entities import BalanceTransactionEntity
from src.balance.enum import TransactionType


class BalanceTransactionRepository:
    """Data-access layer for the immutable balance transaction ledger."""

    def __init__(self, session: AsyncSession) -> None:
        """Initializes the repository with an async SQLAlchemy session.

        Args:
            session: An active async session bound to the current Unit of Work.
        """
        self._session = session

    @staticmethod
    def map_to_entity(model: BalanceTransaction) -> BalanceTransactionEntity:
        """Maps a SQLAlchemy ORM model to a pure domain entity.

        Args:
            model: The hydrated SQLAlchemy BalanceTransaction model.

        Returns:
            A pure Python BalanceTransactionEntity dataclass.
        """
        return BalanceTransactionEntity(
            id=model.id,
            user_id=model.user_id,
            type=model.type,
            amount=model.amount,
            description=model.description,
            idempotency_key=model.idempotency_key,
            created_at=model.created_at,
        )

    @staticmethod
    def map_to_model(entity: BalanceTransactionEntity) -> BalanceTransaction:
        """Maps a pure domain entity to a SQLAlchemy ORM model.

        Args:
            entity: The pure Python BalanceTransactionEntity dataclass.

        Returns:
            An unattached SQLAlchemy BalanceTransaction model.
        """
        return BalanceTransaction(
            id=entity.id,
            user_id=entity.user_id,
            type=entity.type,
            amount=entity.amount,
            description=entity.description,
            idempotency_key=entity.idempotency_key,
            created_at=entity.created_at,
        )

    async def get_by_idempotency_key(
        self, idempotency_key: uuid.UUID
    ) -> BalanceTransactionEntity | None:
        """Fetches a specific transaction by its unique idempotency key.

        Args:
            idempotency_key: The upstream event UUID.

        Returns:
            A BalanceTransactionEntity if a matching record exists, otherwise None.
        """
        stmt = select(BalanceTransaction).where(
            BalanceTransaction.idempotency_key == idempotency_key
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self.map_to_entity(model) if model else None

    async def insert_idempotent(
        self,
        user_id: uuid.UUID,
        amount: int,
        idempotency_key: uuid.UUID,
        description: str | None = None,
    ) -> BalanceTransactionEntity | None:
        """Attempts to insert a new ledger record, ignoring duplicate keys.

        Args:
            user_id: The UUID identifying the user.
            amount: The number of coins involved in the transaction.
            idempotency_key: The upstream event UUID preventing duplicate processing.
            description: Optional contextual note about the transaction.

        Returns:
            A BalanceTransactionEntity if successfully inserted, or None if the
            idempotency_key already exists in the database.
        """
        stmt = (
            pg_insert(BalanceTransaction)
            .values(
                user_id=user_id,
                type=TransactionType.CREDIT,
                amount=amount,
                description=description,
                idempotency_key=idempotency_key,
            )
            .on_conflict_do_nothing(index_elements=["idempotency_key"])
            .returning(BalanceTransaction)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self.map_to_entity(model) if model else None

    async def get_paginated_by_user(
        self, user_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> list[BalanceTransactionEntity]:
        """Retrieves a paginated list of a user's transactions, newest first.

        Args:
            user_id: The UUID identifying the user.
            limit: Maximum number of records to return.
            offset: Number of records to skip.

        Returns:
            A list of BalanceTransactionEntity dataclasses.
        """
        stmt = (
            select(BalanceTransaction)
            .where(BalanceTransaction.user_id == user_id)
            .order_by(BalanceTransaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self.map_to_entity(m) for m in models]

    async def count_by_user(self, user_id: uuid.UUID) -> int:
        """Calculates the total number of transactions for a specific user.

        Args:
            user_id: The UUID identifying the user.

        Returns:
            The integer count of transactions.
        """
        stmt = select(func.count()).select_from(BalanceTransaction).where(
            BalanceTransaction.user_id == user_id
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()