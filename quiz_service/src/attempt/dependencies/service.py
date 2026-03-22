from typing import Annotated
from fastapi import Depends
from src.attempt.service.grading import GradingService
from src.attempt.service.attempt import AttemptService

IGradingService = Annotated[GradingService, Depends()]
IAttemptService = Annotated[AttemptService, Depends()]
