from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.database.engine import db_helper
from src.balance.repositories.balance import BalanceRepository

def _get_balance_repository(session: AsyncSession = Depends(db_helper.get_session)) -> BalanceRepository:
    return BalanceRepository(session)

IBalanceRepository = Annotated[BalanceRepository, Depends(_get_balance_repository)]
