from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status

from src.balance.dto import BalanceResponseDTO, TransactionListResponseDTO
from src.balance.dependencies.service import IBalanceService

balance_router = APIRouter(prefix="/balances", tags=["Balances"])


@balance_router.get(
    "/{user_id}",
    response_model=BalanceResponseDTO,
    status_code=status.HTTP_200_OK,
)
async def get_user_balance(
    user_id: uuid.UUID,
    service: IBalanceService,
) -> BalanceResponseDTO:
    """Retrieves the current balance for a specified user.

    If the user does not have an active balance ledger, a zero-value balance
    is safely initialized and returned.

    Args:
        user_id: The UUID identifying the user.
        service: The injected BalanceService.

    Returns:
        A BalanceResponseDTO containing the user's current coin aggregate.
    """
    return await service.get_balance(user_id)


@balance_router.get(
    "/{user_id}/transactions",
    response_model=TransactionListResponseDTO,
    status_code=status.HTTP_200_OK,
)
async def get_user_transactions(
    user_id: uuid.UUID,
    service: IBalanceService,
    page: int = Query(1, ge=1, description="The 1-based page number to retrieve."),
    page_size: int = Query(
        50, ge=1, le=100, description="The maximum number of transactions per page."
    ),
) -> TransactionListResponseDTO:
    """Retrieves a paginated list of a user's transaction history.

    Transactions are returned in descending chronological order (newest first).

    Args:
        user_id: The UUID identifying the user.
        service: The injected BalanceService.
        page: The requested page index.
        page_size: The pagination page size limit.

    Returns:
        A TransactionListResponseDTO containing the transaction array and
        pagination metadata.
    """
    return await service.get_transactions(
        user_id=user_id,
        page=page,
        page_size=page_size,
    )