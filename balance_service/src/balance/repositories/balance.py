from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.config.database.session import AsyncSession
from src.balance.models.balance import Balance, BalanceTransaction
from src.balance.entities import BalanceEntity, BalanceTransactionEntity
from shared.logging import get_logger

logger = get_logger(__name__)


def _map_balance_entity(db_obj: Balance) -> BalanceEntity:
    return BalanceEntity(
        id=db_obj.id,
        user_id=db_obj.user_id,
        amount=db_obj.amount,
        updated_at=db_obj.updated_at,
    )


def _map_txn_entity(db_obj: BalanceTransaction) -> BalanceTransactionEntity:
    return BalanceTransactionEntity(
        id=db_obj.id,
        user_id=db_obj.user_id,
        type=db_obj.type,
        amount=db_obj.amount,
        description=db_obj.description,
        idempotency_key=db_obj.idempotency_key,
        created_at=db_obj.created_at,
    )


class BalanceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(self, user_id: uuid.UUID) -> BalanceEntity | None:
        result = await self._session.execute(
            select(Balance).where(Balance.user_id == user_id)
        )
        obj = result.scalar_one_or_none()
        return _map_balance_entity(obj) if obj else None

    async def upsert_credit(
        self,
        user_id: uuid.UUID,
        amount: int,
        idempotency_key: uuid.UUID,
        description: str | None = None,
    ) -> BalanceEntity:
        # Step 1: Insert transaction
        txn_stmt = (
            pg_insert(BalanceTransaction)
            .values(
                user_id=user_id,
                type="credit",
                amount=amount,
                description=description,
                idempotency_key=idempotency_key,
            )
            .on_conflict_do_nothing(index_elements=["idempotency_key"])
            .returning(BalanceTransaction.id)
        )
        txn_result = await self._session.execute(txn_stmt)
        inserted_txn_id = txn_result.scalar_one_or_none()

        if inserted_txn_id is None:
            logger.info(
                "Duplicate idempotency key — skipping credit",
                idempotency_key=str(idempotency_key),
                user_id=str(user_id),
            )
            balance = await self.get_by_user_id(user_id)
            if balance is None:
                # Edge case: transaction exists but balance doesn't (shouldn't happen)
                new_balance = Balance(user_id=user_id, amount=0)
                self._session.add(new_balance)
                await self._session.flush()
                balance = _map_balance_entity(new_balance)
            return balance

        # Step 2: Upsert balance
        balance_stmt = (
            pg_insert(Balance)
            .values(user_id=user_id, amount=amount)
            .on_conflict_do_update(
                index_elements=["user_id"],
                set_={"amount": Balance.amount + amount},
            )
            .returning(Balance)
        )
        result = await self._session.execute(balance_stmt)
        balance = result.scalar_one()
        await self._session.flush()

        logger.info(
            "Balance credited",
            user_id=str(user_id),
            amount=amount,
            new_balance=balance.amount,
            idempotency_key=str(idempotency_key),
        )
        return _map_balance_entity(balance)

    async def get_transactions(
        self, user_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> list[BalanceTransactionEntity]:
        result = await self._session.execute(
            select(BalanceTransaction)
            .where(BalanceTransaction.user_id == user_id)
            .order_by(BalanceTransaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [_map_txn_entity(obj) for obj in result.scalars().all()]
