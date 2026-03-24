"""FastAPI dependency aliases for balance service injection.

Provides the :data:`IBalanceService` type alias used by route handlers to
declare a :class:`~src.balance.service.balance.BalanceService` dependency.
FastAPI resolves ``Depends()`` automatically, constructing the service with
the repository resolved from
:data:`~src.balance.dependencies.repository.IBalanceRepository`.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from src.balance.service.balance import BalanceService

IBalanceService: type[BalanceService] = Annotated[BalanceService, Depends()]
"""FastAPI-injected :class:`BalanceService` dependency.

Usage::

    async def my_endpoint(service: IBalanceService) -> ...:
        ...

FastAPI constructs :class:`BalanceService` by resolving its ``repo``
argument via :data:`~src.balance.dependencies.repository.IBalanceRepository`,
which in turn is wired to the per-request database session.
"""
