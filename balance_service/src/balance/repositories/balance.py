from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from shared.exceptions import IdempotencyMismatchError
from src.config.database.session import ISession
from src.balance.models.balance import Balance, BalanceTransaction
from src.balance.entities import BalanceEntity, BalanceTransactionEntity
from shared.logging import get_logger

logger = get_logger(__name__)


def _map_balance_entity(db_obj: Balance) -> BalanceEntity:
    """Convert a `Balance` ORM instance to a `BalanceEntity`.

    Args:
        db_obj: A hydrated SQLAlchemy ``Balance`` model retrieved from the DB.

    Returns:
        A `BalanceEntity` dataclass populated with the ORM object's data.
    """
    return BalanceEntity(
        id=db_obj.id,
        user_id=db_obj.user_id,
        amount=db_obj.amount,
        updated_at=db_obj.updated_at,
    )


def _map_txn_entity(db_obj: BalanceTransaction) -> BalanceTransactionEntity:
    """Convert a `BalanceTransaction` ORM instance to a `BalanceTransactionEntity`.

    Args:
        db_obj: A hydrated SQLAlchemy ``BalanceTransaction`` model retrieved
            from the DB.

    Returns:
        A `BalanceTransactionEntity` dataclass populated with the ORM
        object's data.
    """
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
    """Data-access layer for balance and transaction records.

    All SQL operations are executed through the injected async SQLAlchemy
    session (``ISession``). The repository is responsible for:

    - Fetching a user's current balance.
    - Atomically inserting a transaction and upserting the aggregate balance,
      with full idempotency (duplicate events are silently skipped).
    - Retrieving a paginated, newest-first list of transactions.

    The repository does **not** commit the session; that responsibility belongs
    to the caller (router via FastAPI dependency injection or consumer via
    ``session.begin()``).
    """

    def __init__(self, session: ISession) -> None:
        """Initialise the repository with an async SQLAlchemy session.

        Args:
            session: An active ``AsyncSession`` bound to the current unit of
                work. Typically injected by FastAPI's dependency system or
                provided via ``db_helper.get_db_session()`` in the consumer.
        """
        self._session = session

    async def get_by_user_id(self, user_id: uuid.UUID) -> BalanceEntity | None:
        """Fetch the balance record for a given user.

        Args:
            user_id: The UUID identifying the user whose balance is to retrieve.

        Returns:
            A `BalanceEntity` if a balance record exists, or ``None``
            if the user has never been credited.
        """
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
        """Atomically record a credit transaction and update the aggregate balance.

        Guarantees exactly-once semantics: if ``idempotency_key`` has already
        been used, the transaction insert is skipped, and the current balance is
        returned unchanged.

        Args:
            user_id: The UUID of the user to credit.
            amount: Number of coins to add (``>= 0``).
            idempotency_key: Unique key (usually the upstream event UUID) that
                prevents double-application of the same credit.
            description: Optional human-readable annotation stored on the
                transaction record.

        Returns:
            The updated (or unchanged, for duplicates) `BalanceEntity`.
        """
        is_new = await self._try_insert_transaction(
            user_id=user_id,
            amount=amount,
            idempotency_key=idempotency_key,
            description=description,
        )

        if not is_new:
            existing_txn = await self._get_transaction_by_idempotency_key(idempotency_key)

            if existing_txn and existing_txn.amount != amount:
                logger.warning(
                    "Idempotency mismatch detected",
                    idempotency_key=str(idempotency_key),
                    old_amount=existing_txn.amount,
                    new_amount=amount,
                )
                raise IdempotencyMismatchError(
                    f"Idempotency key {idempotency_key} was already used "
                    f"for {existing_txn.amount} coins. Cannot process for {amount}."
                )

            logger.info(
                "Duplicate idempotency key — returning current balance safely",
                idempotency_key=str(idempotency_key),
                user_id=str(user_id),
            )
            return await self._get_current_balance_or_seed(user_id)

        balance = await self._apply_balance_credit(user_id=user_id, amount=amount)

        logger.info(
            "Balance credited",
            user_id=str(user_id),
            amount=amount,
            new_balance=balance.amount,
            idempotency_key=str(idempotency_key),
        )
        return balance

    async def _get_transaction_by_idempotency_key(
            self, idempotency_key: uuid.UUID
    ) -> BalanceTransactionEntity | None:
        """Helper to fetch an existing transaction by its unique key."""
        result = await self._session.execute(
            select(BalanceTransaction).where(BalanceTransaction.idempotency_key == idempotency_key)
        )
        obj = result.scalar_one_or_none()
        return _map_txn_entity(obj) if obj else None

    async def get_transactions(
        self, user_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> list[BalanceTransactionEntity]:
        """Retrieve a paginated, newest-first list of transactions for a user.

        Args:
            user_id: The UUID of the user whose transactions to retrieve.
            limit: Maximum number of rows to return. Defaults to ``50``.
            offset: Number of rows to skip (for pagination). Defaults to ``0``.

        Returns:
            A list of `BalanceTransactionEntity` objects ordered by
            ``created_at DESC``. Returns an empty list if no transactions exist.
        """
        result = await self._session.execute(
            select(BalanceTransaction)
            .where(BalanceTransaction.user_id == user_id)
            .order_by(BalanceTransaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [_map_txn_entity(obj) for obj in result.scalars().all()]

    async def _try_insert_transaction(
        self,
        user_id: uuid.UUID,
        amount: int,
        idempotency_key: uuid.UUID,
        description: str | None,
    ) -> bool:
        """Attempt to insert a transaction row, skipping silently on duplicates.

        Uses ``INSERT … ON CONFLICT DO NOTHING`` on ``idempotency_key`` so that
        re-delivering the same event never creates a second ledger entry.

        Args:
            user_id: Owner of the transaction.
            amount: Coin amount involved in the transaction.
            idempotency_key: Unique key guarding against duplicate inserts.
            description: Optional annotation attached to the record.

        Returns:
            ``True`` if the row was newly inserted, ``False`` if it already
            existed (duplicate event).
        """
        stmt = (
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
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def _apply_balance_credit(
        self, user_id: uuid.UUID, amount: int
    ) -> BalanceEntity:
        """Upsert the aggregate balance by adding ``amount`` to the current total.

        Creates the balance row on first credit; increments it on subsequent
        ones. Uses ``INSERT … ON CONFLICT DO UPDATE`` for an atomic upsert
        without a separate SELECT.

        Args:
            user_id: Owner of the balance to update.
            amount: Number of coins to add.

        Returns:
            The updated `BalanceEntity` reflecting the new total.
        """
        stmt = (
            pg_insert(Balance)
            .values(user_id=user_id, amount=amount)
            .on_conflict_do_update(
                index_elements=["user_id"],
                set_={"amount": Balance.amount + amount},
            )
            .returning(Balance)
        )
        result = await self._session.execute(stmt)
        balance = result.scalar_one()
        return _map_balance_entity(balance)

    async def _get_current_balance_or_seed(self, user_id: uuid.UUID) -> BalanceEntity:
        """Return the existing balance or safely create a zero-value one.

        Optimized to avoid PostgreSQL write-amplification (MVCC row duplication)
        by attempting a fast, lock-free SELECT before falling back to an insert.
        """
        existing_balance = await self.get_by_user_id(user_id)
        if existing_balance is not None:
            return existing_balance

        stmt = (
            pg_insert(Balance)
            .values(user_id=user_id, amount=0)
            .on_conflict_do_nothing(index_elements=["user_id"])
            .returning(Balance)
        )
        result = await self._session.execute(stmt)
        new_balance = result.scalar_one_or_none()

        if new_balance is not None:
            return _map_balance_entity(new_balance)

        concurrent_balance = await self.get_by_user_id(user_id)
        if concurrent_balance is None:
            raise RuntimeError(f"Failed to seed or retrieve balance for user {user_id}")

        return concurrent_balance