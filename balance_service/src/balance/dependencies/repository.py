"""FastAPI dependency aliases for balance repository injection.

Provides the :data:`IBalanceRepository` type alias used throughout the API
layer to declare a :class:`~src.balance.repositories.balance.BalanceRepository`
dependency. FastAPI resolves the annotated ``Depends()`` automatically,
constructing the repository with the session from
:data:`~src.config.database.session.ISession`.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from src.config.database.session import ISession
from src.balance.repositories.balance import BalanceRepository

IBalanceRepository = Annotated[BalanceRepository, Depends()]
"""FastAPI-injected :class:`BalanceRepository` dependency.

Usage::

    async def my_endpoint(repo: IBalanceRepository) -> ...:
        ...

FastAPI constructs :class:`BalanceRepository` by inspecting its
``__init__`` signature and resolving ``session: ISession`` automatically,
giving every request handler its own per-request session.
"""
