from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from src.balance.service.balance import BalanceService

IBalanceService: type[BalanceService] = Annotated[BalanceService, Depends()]
