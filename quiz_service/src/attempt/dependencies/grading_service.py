from typing import Annotated
from fastapi import Depends

from src.attempt.service.grading import GradingService

IGradingService = Annotated[GradingService, Depends()]