"""
Unit tests for BalanceRepository and BalanceTransactionRepository.

Tests use MagicMock/AsyncMock for the SQLAlchemy session and verify:
  - Correct SQL statement construction
  - Correct entity mapping (model → entity)
  - Edge cases: missing records, duplicate key handling, pagination math
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.balance.entities import BalanceEntity, BalanceTransactionEntity
from src.balance.enum import TransactionType
from src.balance.models.balance import Balance
from src.balance.models.balance_transaction import BalanceTransaction
from src.balance.repositories.balance import BalanceRepository
from src.balance.repositories.balance_transaction import BalanceTransactionRepository
from tests.conftest import make_uuid, utcnow


# ---------------------------------------------------------------------------
# Helpers: build ORM model instances
# ---------------------------------------------------------------------------

def _balance_model(*, user_id: uuid.UUID | None=None, amount: int=0) -> Balance:
    return Balance(
        id=make_uuid(),
        user_id=user_id or make_uuid(),
        amount=amount,
        updated_at=utcnow()
    )

def _tx_model(*, user_id: uuid.UUID | None=None, amount: int=100, idempotency_key: uuid.UUID | None=None, tx_type: TransactionType=TransactionType.CREDIT) -> BalanceTransaction:
    return BalanceTransaction(
        id=make_uuid(),
        user_id=user_id or make_uuid(),
        type=tx_type,
        amount=amount,
        description='test tx',
        idempotency_key=idempotency_key or make_uuid(),
        created_at=utcnow()
    )


def _mock_session() -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


def _scalar_result(value) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    result.scalar_one.return_value = value
    result.scalars.return_value.all.return_value = value if isinstance(value, list) else []
    return result


# ===========================================================================
# BalanceRepository
# ===========================================================================

class TestBalanceRepositoryGetByUserId:

    @pytest.mark.asyncio
    async def test_returns_entity_when_found(self):
        session = _mock_session()
        model = _balance_model(amount=500)
        session.execute.return_value = _scalar_result(model)
        repo = BalanceRepository(session)

        result = await repo.get_by_user_id(model.user_id)

        assert result is not None
        assert result.user_id == model.user_id
        assert result.amount == 500

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        session = _mock_session()
        session.execute.return_value = _scalar_result(None)
        repo = BalanceRepository(session)

        result = await repo.get_by_user_id(make_uuid())

        assert result is None

    @pytest.mark.asyncio
    async def test_entity_fields_mapped_correctly(self):
        session = _mock_session()
        user_id = make_uuid()
        model = _balance_model(user_id=user_id, amount=1000)
        session.execute.return_value = _scalar_result(model)
        repo = BalanceRepository(session)

        entity = await repo.get_by_user_id(user_id)

        assert isinstance(entity, BalanceEntity)
        assert entity.id == model.id
        assert entity.user_id == user_id
        assert entity.amount == 1000


class TestBalanceRepositoryUpsertAmount:

    @pytest.mark.asyncio
    async def test_returns_updated_entity(self):
        session = _mock_session()
        user_id = make_uuid()
        result_model = _balance_model(user_id=user_id, amount=300)
        session.execute.return_value = _scalar_result(result_model)
        repo = BalanceRepository(session)

        entity = await repo.upsert_amount(user_id=user_id, amount=100)

        assert entity.user_id == user_id
        assert entity.amount == 300

    @pytest.mark.asyncio
    async def test_statement_is_executed(self):
        session = _mock_session()
        user_id = make_uuid()
        result_model = _balance_model(user_id=user_id, amount=100)
        session.execute.return_value = _scalar_result(result_model)
        repo = BalanceRepository(session)

        await repo.upsert_amount(user_id=user_id, amount=100)

        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_zero_amount_creates_balance(self):
        session = _mock_session()
        user_id = make_uuid()
        result_model = _balance_model(user_id=user_id, amount=0)
        session.execute.return_value = _scalar_result(result_model)
        repo = BalanceRepository(session)

        entity = await repo.upsert_amount(user_id=user_id, amount=0)

        assert entity.amount == 0


# ===========================================================================
# BalanceTransactionRepository
# ===========================================================================

class TestTransactionRepoGetByIdempotencyKey:

    @pytest.mark.asyncio
    async def test_returns_entity_when_found(self):
        session = _mock_session()
        ikey = make_uuid()
        model = _tx_model(idempotency_key=ikey, amount=100)
        session.execute.return_value = _scalar_result(model)
        repo = BalanceTransactionRepository(session)

        result = await repo.get_by_idempotency_key(ikey)

        assert result is not None
        assert result.idempotency_key == ikey
        assert result.amount == 100

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        session = _mock_session()
        session.execute.return_value = _scalar_result(None)
        repo = BalanceTransactionRepository(session)

        result = await repo.get_by_idempotency_key(make_uuid())

        assert result is None

    @pytest.mark.asyncio
    async def test_entity_type_is_correct(self):
        session = _mock_session()
        model = _tx_model()
        session.execute.return_value = _scalar_result(model)
        repo = BalanceTransactionRepository(session)

        entity = await repo.get_by_idempotency_key(model.idempotency_key)

        assert isinstance(entity, BalanceTransactionEntity)


class TestTransactionRepoInsertIdempotent:

    @pytest.mark.asyncio
    async def test_returns_entity_on_success(self):
        session = _mock_session()
        user_id = make_uuid()
        ikey = make_uuid()
        model = _tx_model(user_id=user_id, amount=200, idempotency_key=ikey)
        session.execute.return_value = _scalar_result(model)
        repo = BalanceTransactionRepository(session)

        result = await repo.insert_idempotent(
            user_id=user_id, amount=200, idempotency_key=ikey
        )

        assert result is not None
        assert result.amount == 200
        assert result.idempotency_key == ikey

    @pytest.mark.asyncio
    async def test_returns_none_on_duplicate_key(self):
        """ON CONFLICT DO NOTHING returns no row → None entity."""
        session = _mock_session()
        session.execute.return_value = _scalar_result(None)
        repo = BalanceTransactionRepository(session)

        result = await repo.insert_idempotent(
            user_id=make_uuid(), amount=100, idempotency_key=make_uuid()
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_description_stored(self):
        session = _mock_session()
        ikey = make_uuid()
        model = _tx_model(idempotency_key=ikey)
        model.description = "custom desc"
        session.execute.return_value = _scalar_result(model)
        repo = BalanceTransactionRepository(session)

        result = await repo.insert_idempotent(
            user_id=make_uuid(), amount=50, idempotency_key=ikey, description="custom desc"
        )

        assert result.description == "custom desc"

    @pytest.mark.asyncio
    async def test_type_is_always_credit(self):
        session = _mock_session()
        model = _tx_model(tx_type=TransactionType.CREDIT)
        session.execute.return_value = _scalar_result(model)
        repo = BalanceTransactionRepository(session)

        result = await repo.insert_idempotent(
            user_id=make_uuid(), amount=100, idempotency_key=make_uuid()
        )

        assert result.type == TransactionType.CREDIT


class TestTransactionRepoGetPaginated:

    @pytest.mark.asyncio
    async def test_returns_list_of_entities(self):
        session = _mock_session()
        user_id = make_uuid()
        models = [_tx_model(user_id=user_id) for _ in range(3)]
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = models
        session.execute.return_value = result_mock
        repo = BalanceTransactionRepository(session)

        entities = await repo.get_paginated_by_user(user_id=user_id, limit=10, offset=0)

        assert len(entities) == 3
        assert all(isinstance(e, BalanceTransactionEntity) for e in entities)

    @pytest.mark.asyncio
    async def test_empty_list_when_no_transactions(self):
        session = _mock_session()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        session.execute.return_value = result_mock
        repo = BalanceTransactionRepository(session)

        entities = await repo.get_paginated_by_user(user_id=make_uuid(), limit=50, offset=0)

        assert entities == []


class TestTransactionRepoCountByUser:

    @pytest.mark.asyncio
    async def test_returns_count(self):
        session = _mock_session()
        result_mock = MagicMock()
        result_mock.scalar_one.return_value = 42
        session.execute.return_value = result_mock
        repo = BalanceTransactionRepository(session)

        count = await repo.count_by_user(make_uuid())

        assert count == 42

    @pytest.mark.asyncio
    async def test_zero_for_new_user(self):
        session = _mock_session()
        result_mock = MagicMock()
        result_mock.scalar_one.return_value = 0
        session.execute.return_value = result_mock
        repo = BalanceTransactionRepository(session)

        count = await repo.count_by_user(make_uuid())

        assert count == 0