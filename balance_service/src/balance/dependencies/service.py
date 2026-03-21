from typing import Annotated

from fastapi import Depends

from src.balance.service.balance import BalanceService

IBalanceService = Annotated[BalanceService, Depends()]
