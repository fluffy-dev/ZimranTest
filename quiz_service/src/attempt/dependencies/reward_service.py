from typing import Annotated
from fastapi import Depends
from src.attempt.service.reward import RewardService

IRewardService: type[RewardService] = Annotated[RewardService, Depends()]
