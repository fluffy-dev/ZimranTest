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
