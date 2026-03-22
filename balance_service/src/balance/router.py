from __future__ import annotations

from fastapi import APIRouter, Query

from src.dependencies.common import IUserID
from src.balance.dependencies.service import IBalanceService
from src.balance.dto import BalanceResponseDTO, TransactionListResponseDTO, TransactionResponseDTO

router = APIRouter(prefix="/balance", tags=["Balance"])


@router.get("", response_model=BalanceResponseDTO, summary="Get current balance")
async def get_balance(
    user_id: IUserID,
    service: IBalanceService,
) -> BalanceResponseDTO:
    """Return the caller's current virtual coin balance.

    Reads the ``X-User-ID`` header (injected as ``user_id`` via
    :data:`~src.dependencies.common.IUserID`) and fetches the user's balance
    from the service layer. If the user has no balance record yet, one is
    transparently created with ``amount=0``.

    Args:
        user_id: Caller's UUID extracted and validated from the
            ``X-User-ID`` request header.
        service: Injected :class:`~src.balance.service.balance.BalanceService`
            instance.

    Returns:
        A :class:`~src.balance.dto.BalanceResponseDTO` containing ``user_id``,
        current ``amount``, and ``updated_at`` timestamp.
    """
    balance = await service.get_balance(user_id=user_id)
    return BalanceResponseDTO(
        user_id=balance.user_id,
        amount=balance.amount,
        updated_at=balance.updated_at,
    )


@router.get("/transactions", response_model=TransactionListResponseDTO, summary="Transaction history")
async def get_transactions(
    user_id: IUserID,
    service: IBalanceService,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> TransactionListResponseDTO:
    """Return a paginated, newest-first list of the caller's transactions.

    Reads the ``X-User-ID`` header for the user identity and delegates to
    the service layer for pagination and retrieval. Transactions are sorted
    by ``created_at DESC``.

    Args:
        user_id: Caller's UUID extracted and validated from the
            ``X-User-ID`` request header.
        service: Injected :class:`~src.balance.service.balance.BalanceService`
            instance.
        page: 1-based page number to retrieve. Must be ``>= 1``.
            Defaults to ``1``.
        page_size: Number of records to return per page. Must be between
            ``1`` and ``100`` inclusive. Defaults to ``50``.

    Returns:
        A :class:`~src.balance.dto.TransactionListResponseDTO` containing the
        paginated ``items`` list along with echoed ``page`` and ``page_size``
        metadata.
    """
    txns = await service.get_transactions(user_id=user_id, page=page, page_size=page_size)
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
            for t in txns
        ],
        page=page,
        page_size=page_size,
    )
