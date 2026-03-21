from typing import Annotated

from fastapi import Depends
from src.config.database.session import ISession
from src.balance.repositories.balance import BalanceRepository

def _get_balance_repository(session: ISession) -> BalanceRepository:
    return BalanceRepository(session)

IBalanceRepository = Annotated[BalanceRepository, Depends(_get_balance_repository)]
