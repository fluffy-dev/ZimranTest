"""Repository dependency type aliases for balance service."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.repositories.balance_repository import BalanceRepository


IBalanceRepository = Annotated[BalanceRepository, Depends()]
