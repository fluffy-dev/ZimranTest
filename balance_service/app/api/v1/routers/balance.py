from __future__ import annotations

from fastapi import APIRouter, Query

from app.dependencies.common import IUserID
from app.dependencies.services import IBalanceService
from app.schemas.balance import BalanceResponse, TransactionListResponse, TransactionResponse

router = APIRouter(prefix="/balance", tags=["Balance"])


@router.get("", response_model=BalanceResponse, summary="Get current balance")
async def get_balance(
    user_id: IUserID,
    service: IBalanceService,
) -> BalanceResponse:
    balance = await service.get_balance(user_id=user_id)
    return BalanceResponse(
        user_id=balance.user_id,
        amount=balance.amount,
        updated_at=balance.updated_at,
    )


@router.get("/transactions", response_model=TransactionListResponse, summary="Transaction history")
async def get_transactions(
    user_id: IUserID,
    service: IBalanceService,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> TransactionListResponse:
    txns = await service.get_transactions(user_id=user_id, page=page, page_size=page_size)
    return TransactionListResponse(
        items=[
            TransactionResponse(
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
