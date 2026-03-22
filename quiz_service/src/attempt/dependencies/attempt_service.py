from typing import Annotated
from fastapi import Depends

from src.attempt.service.attempt import AttemptService
IAttemptService = Annotated[AttemptService, Depends()]
