from typing import Annotated

from fastapi import Depends
from src.config.database.session import ISession
from src.attempt.repositories.attempt import AttemptRepository
from src.attempt.repositories.outbox import OutboxRepository

IAttemptRepository = Annotated[AttemptRepository, Depends()]
IOutboxRepository = Annotated[OutboxRepository, Depends()]
