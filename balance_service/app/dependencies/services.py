"""Service dependency type aliases for balance service."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.services.balance_service import BalanceService


IBalanceService = Annotated[BalanceService, Depends()]
