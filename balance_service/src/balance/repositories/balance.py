from __future__ import annotations

import uuid

from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from sqlalchemy.ext.asyncio import AsyncSession
from src.balance.models.balance import Balance
from src.balance.entities import BalanceEntity


class BalanceRepository:
    """Data-access layer for the mutable user balance aggregate."""

    def __init__(self, session: AsyncSession) -> None:
        """Initializes the repository with an async SQLAlchemy session.

        Args:
            session: An active async session bound to the current Unit of Work.
        """
        self._session = session

    @staticmethod
    def map_to_entity(model: Balance) -> BalanceEntity:
        """Maps a SQLAlchemy ORM model to a pure domain entity.

        Args:
            model: The hydrated SQLAlchemy Balance model.

        Returns:
            A pure Python BalanceEntity dataclass.
        """
        return BalanceEntity(
            id=model.id,
            user_id=model.user_id,
            amount=model.amount,
            updated_at=model.updated_at,
        )

    @staticmethod
    def map_to_model(entity: BalanceEntity) -> Balance:
        """Maps a pure domain entity to a SQLAlchemy ORM model.

        Args:
            entity: The pure Python BalanceEntity dataclass.

        Returns:
            An unattached SQLAlchemy Balance model.
        """
        return Balance(
            id=entity.id,
            user_id=entity.user_id,
            amount=entity.amount,
            updated_at=entity.updated_at,
        )

    async def get_by_user_id(self, user_id: uuid.UUID) -> BalanceEntity | None:
        """Fetches the current balance record for a given user.

        Args:
            user_id: The UUID identifying the user.

        Returns:
            A BalanceEntity if found, otherwise None.
        """
        stmt = select(Balance).where(Balance.user_id == user_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self.map_to_entity(model) if model else None

    async def upsert_amount(self, user_id: uuid.UUID, amount: int) -> BalanceEntity:
        """Atomically increments the user's balance or creates it if missing.

        Args:
            user_id: The UUID identifying the user.
            amount: The number of coins to add to the aggregate balance.

        Returns:
            A BalanceEntity reflecting the newly updated aggregate total.
        """
        stmt = (
            pg_insert(Balance)
            .values(user_id=user_id, amount=amount)
            .on_conflict_do_update(
                index_elements=["user_id"],
                set_={
                    "amount": Balance.amount + amount,
                    "updated_at": func.now(),
                },
            )
            .returning(Balance)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one()
        return self.map_to_entity(model)