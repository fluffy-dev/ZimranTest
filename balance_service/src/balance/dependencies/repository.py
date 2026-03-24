
from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from src.balance.repositories.balance import BalanceRepository

IBalanceRepository: type[BalanceRepository] = Annotated[BalanceRepository, Depends()]
