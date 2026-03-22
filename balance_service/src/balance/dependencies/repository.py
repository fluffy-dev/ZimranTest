from typing import Annotated

from fastapi import Depends
from src.config.database.session import ISession
from src.balance.repositories.balance import BalanceRepository

IBalanceRepository = Annotated[BalanceRepository, Depends()]
