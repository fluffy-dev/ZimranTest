from typing import Annotated
from fastapi import Depends
from src.uow import IUnitOfWork
from src.attempt.service.attempt import AttemptService
from src.attempt.dependencies.reward_service import IRewardService

IAttemptService: type[AttemptService] = Annotated[AttemptService, Depends()]
