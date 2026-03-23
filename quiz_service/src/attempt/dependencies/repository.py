from typing import Annotated

from fastapi import Depends
from src.attempt.repositories.attempt import AttemptRepository
from src.attempt.repositories.outbox import OutboxRepository

IAttemptRepository: type[AttemptRepository] = Annotated[AttemptRepository, Depends()]
IOutboxRepository: type[OutboxRepository] = Annotated[OutboxRepository, Depends()]
