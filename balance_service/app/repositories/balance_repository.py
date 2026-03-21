from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.dependencies.common import ISession
from app.db.models import Balance, BalanceTransaction
from shared.logging import get_logger

logger = get_logger(__name__)


class BalanceRepository:
    def __init__(self, session: ISession) -> None:
        self._session = session

    async def get_by_user_id(self, user_id: uuid.UUID) -> Balance | None:
        result = await self._session.execute(
            select(Balance).where(Balance.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def upsert_credit(
        self,
        user_id: uuid.UUID,
        amount: int,
        idempotency_key: uuid.UUID,
        description: str | None = None,
    ) -> Balance:
        """
        Atomically credits user balance and records the transaction.

        Two-step idempotency:
        1. INSERT INTO balance_transactions ... ON CONFLICT (idempotency_key) DO NOTHING
           - If idempotency_key already exists → transaction aborted → balance NOT updated
        2. INSERT INTO balances ... ON CONFLICT (user_id) DO UPDATE SET amount = amount + excluded.amount
           - Creates balance if not exists, or increments it

        This is safe for concurrent requests and RabbitMQ at-least-once delivery.
        """
        # Step 1: Insert transaction (idempotent guard)
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
            # Already processed — return current balance without modifying
            logger.info(
                "Duplicate idempotency key — skipping credit",
                idempotency_key=str(idempotency_key),
                user_id=str(user_id),
            )
            balance = await self.get_by_user_id(user_id)
            if balance is None:
                # Edge case: transaction exists but balance doesn't (shouldn't happen)
                balance = Balance(user_id=user_id, amount=0)
                self._session.add(balance)
                await self._session.flush()
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
        return balance

    async def get_transactions(
        self, user_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> list[BalanceTransaction]:
        result = await self._session.execute(
            select(BalanceTransaction)
            .where(BalanceTransaction.user_id == user_id)
            .order_by(BalanceTransaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
