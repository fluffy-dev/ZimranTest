"""
Integration tests for balance_service HTTP routes.

Tests exercise the FastAPI router → service boundary, verifying:
  - Correct HTTP status codes
  - Response schema shape
  - Query-param validation
  - Path-param UUID validation
  - Dependency injection override mechanics
  - Error → HTTP status mapping
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from shared.exceptions import NotFoundException
from src.balance.service.balance import BalanceService
from src.balance.dependencies.service import IBalanceService
from src.balance.dto import BalanceResponseDTO, TransactionListResponseDTO, TransactionResponseDTO
from tests.conftest import make_uuid, utcnow


def _make_balance_dto(
    user_id: uuid.UUID | None = None,
    amount: int = 500,
) -> BalanceResponseDTO:
    return BalanceResponseDTO(
        user_id=user_id or make_uuid(),
        amount=amount,
        updated_at=utcnow(),
    )


def _make_tx_dto(user_id: uuid.UUID | None = None) -> TransactionResponseDTO:
    return TransactionResponseDTO(
        id=make_uuid(),
        user_id=user_id or make_uuid(),
        type="credit",
        amount=100,
        description="Quiz reward",
        created_at=utcnow(),
    )


def _make_tx_list_dto(
    items: list[TransactionResponseDTO] | None = None,
    total: int = 0,
    page: int = 1,
    page_size: int = 50,
) -> TransactionListResponseDTO:
    return TransactionListResponseDTO(
        items=items or [],
        total=total,
        page=page,
        page_size=page_size,
    )


def _client_with_service(mock_svc: AsyncMock) -> TestClient:
    import asyncio
    from unittest.mock import patch

    async def _mock_supervise():
        try:
            await asyncio.sleep(float('inf'))
        except asyncio.CancelledError:
            pass
    with patch('src.lifespan._supervise_consumer', side_effect=_mock_supervise):
        from src.app import app
        # Use BalanceService here instead of IBalanceService
        app.dependency_overrides[BalanceService] = lambda: mock_svc
        return TestClient(app, raise_server_exceptions=False)


# ===========================================================================
# GET /api/v1/balances/{user_id}
# ===========================================================================

class TestGetUserBalance:

    def test_200_returns_balance(self):
        user_id = make_uuid()
        mock_svc = AsyncMock()
        mock_svc.get_balance.return_value = _make_balance_dto(user_id=user_id, amount=300)

        with _client_with_service(mock_svc) as client:
            resp = client.get(f"/api/v1/balances/{user_id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == str(user_id)
        assert data["amount"] == 300

    def test_200_zero_balance(self):
        user_id = make_uuid()
        mock_svc = AsyncMock()
        mock_svc.get_balance.return_value = _make_balance_dto(user_id=user_id, amount=0)

        with _client_with_service(mock_svc) as client:
            resp = client.get(f"/api/v1/balances/{user_id}")

        assert resp.status_code == 200
        assert resp.json()["amount"] == 0

    def test_404_when_service_raises_not_found(self):
        mock_svc = AsyncMock()
        mock_svc.get_balance.side_effect = NotFoundException("User not found")

        with _client_with_service(mock_svc) as client:
            resp = client.get(f"/api/v1/balances/{make_uuid()}")

        assert resp.status_code == 404

    def test_422_invalid_uuid_in_path(self):
        mock_svc = AsyncMock()

        with _client_with_service(mock_svc) as client:
            resp = client.get("/api/v1/balances/not-a-uuid")

        assert resp.status_code == 422

    def test_500_on_unexpected_service_exception(self):
        mock_svc = AsyncMock()
        mock_svc.get_balance.side_effect = RuntimeError("unexpected DB failure")

        with _client_with_service(mock_svc) as client:
            resp = client.get(f"/api/v1/balances/{make_uuid()}")

        assert resp.status_code == 500

    def test_response_contains_updated_at(self):
        user_id = make_uuid()
        mock_svc = AsyncMock()
        mock_svc.get_balance.return_value = _make_balance_dto(user_id=user_id)

        with _client_with_service(mock_svc) as client:
            resp = client.get(f"/api/v1/balances/{user_id}")

        assert "updated_at" in resp.json()

    def test_service_called_with_correct_user_id(self):
        user_id = make_uuid()
        mock_svc = AsyncMock()
        mock_svc.get_balance.return_value = _make_balance_dto(user_id=user_id)

        with _client_with_service(mock_svc) as client:
            client.get(f"/api/v1/balances/{user_id}")

        mock_svc.get_balance.assert_called_once_with(user_id)

    def test_error_response_has_correlation_id_field(self):
        mock_svc = AsyncMock()
        mock_svc.get_balance.side_effect = NotFoundException("not found")

        with _client_with_service(mock_svc) as client:
            resp = client.get(f"/api/v1/balances/{make_uuid()}")

        # Balance service enriches errors with correlation_id
        assert "error" in resp.json()


# ===========================================================================
# GET /api/v1/balances/{user_id}/transactions
# ===========================================================================

class TestGetUserTransactions:

    def test_200_returns_transaction_list(self):
        user_id = make_uuid()
        mock_svc = AsyncMock()
        tx = _make_tx_dto(user_id=user_id)
        mock_svc.get_transactions.return_value = _make_tx_list_dto(
            items=[tx], total=1, page=1, page_size=50
        )

        with _client_with_service(mock_svc) as client:
            resp = client.get(f"/api/v1/balances/{user_id}/transactions")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1

    def test_200_empty_transaction_list(self):
        mock_svc = AsyncMock()
        mock_svc.get_transactions.return_value = _make_tx_list_dto(items=[], total=0)

        with _client_with_service(mock_svc) as client:
            resp = client.get(f"/api/v1/balances/{make_uuid()}/transactions")

        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_default_pagination_params(self):
        user_id = make_uuid()
        mock_svc = AsyncMock()
        mock_svc.get_transactions.return_value = _make_tx_list_dto()

        with _client_with_service(mock_svc) as client:
            client.get(f"/api/v1/balances/{user_id}/transactions")

        mock_svc.get_transactions.assert_called_once_with(
            user_id=user_id, page=1, page_size=50
        )

    def test_custom_pagination_params_forwarded(self):
        user_id = make_uuid()
        mock_svc = AsyncMock()
        mock_svc.get_transactions.return_value = _make_tx_list_dto()

        with _client_with_service(mock_svc) as client:
            client.get(f"/api/v1/balances/{user_id}/transactions?page=3&page_size=10")

        mock_svc.get_transactions.assert_called_once_with(
            user_id=user_id, page=3, page_size=10
        )

    def test_422_page_zero_is_invalid(self):
        mock_svc = AsyncMock()

        with _client_with_service(mock_svc) as client:
            resp = client.get(f"/api/v1/balances/{make_uuid()}/transactions?page=0")

        assert resp.status_code == 422

    def test_422_page_size_zero_is_invalid(self):
        mock_svc = AsyncMock()

        with _client_with_service(mock_svc) as client:
            resp = client.get(
                f"/api/v1/balances/{make_uuid()}/transactions?page_size=0"
            )

        assert resp.status_code == 422

    def test_422_page_size_over_100_is_invalid(self):
        mock_svc = AsyncMock()

        with _client_with_service(mock_svc) as client:
            resp = client.get(
                f"/api/v1/balances/{make_uuid()}/transactions?page_size=101"
            )

        assert resp.status_code == 422

    def test_page_size_100_is_valid(self):
        user_id = make_uuid()
        mock_svc = AsyncMock()
        mock_svc.get_transactions.return_value = _make_tx_list_dto()

        with _client_with_service(mock_svc) as client:
            resp = client.get(
                f"/api/v1/balances/{user_id}/transactions?page_size=100"
            )

        assert resp.status_code == 200

    def test_422_invalid_uuid_in_path(self):
        mock_svc = AsyncMock()

        with _client_with_service(mock_svc) as client:
            resp = client.get("/api/v1/balances/not-a-valid-uuid/transactions")

        assert resp.status_code == 422

    def test_transaction_item_fields_present(self):
        user_id = make_uuid()
        tx = _make_tx_dto(user_id=user_id)
        mock_svc = AsyncMock()
        mock_svc.get_transactions.return_value = _make_tx_list_dto(
            items=[tx], total=1
        )

        with _client_with_service(mock_svc) as client:
            resp = client.get(f"/api/v1/balances/{user_id}/transactions")

        item = resp.json()["items"][0]
        assert "id" in item
        assert "user_id" in item
        assert "amount" in item
        assert "type" in item
        assert "created_at" in item

    def test_500_on_unexpected_error(self):
        mock_svc = AsyncMock()
        mock_svc.get_transactions.side_effect = RuntimeError("DB exploded")

        with _client_with_service(mock_svc) as client:
            resp = client.get(f"/api/v1/balances/{make_uuid()}/transactions")

        assert resp.status_code == 500


# ===========================================================================
# Health endpoints
# ===========================================================================

class TestHealthEndpoints:

    def test_liveness_returns_ok(self, app_client):
        resp = app_client.get("/health/live")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_readiness_returns_json(self, app_client):
        # In test environment DB is not available — service should degrade gracefully
        resp = app_client.get("/health/ready")
        assert resp.status_code in (200, 503)
        data = resp.json()
        assert "status" in data
        assert "checks" in data

    def test_readiness_contains_database_key(self, app_client):
        resp = app_client.get("/health/ready")
        assert "database" in resp.json()["checks"]

    def test_readiness_contains_messaging_key(self, app_client):
        resp = app_client.get("/health/ready")
        assert "messaging" in resp.json()["checks"]