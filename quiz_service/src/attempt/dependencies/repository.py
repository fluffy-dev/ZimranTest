from typing import Annotated

from fastapi import Depends
from src.config.database.session import ISession
from src.attempt.repositories.attempt import AttemptRepository
from src.attempt.repositories.outbox import OutboxRepository

def _get_attempt_repository(session: ISession) -> AttemptRepository:
    return AttemptRepository(session)

def _get_outbox_repository(session: ISession) -> OutboxRepository:
    return OutboxRepository(session)

IAttemptRepository = Annotated[AttemptRepository, Depends(_get_attempt_repository)]
IOutboxRepository = Annotated[OutboxRepository, Depends(_get_outbox_repository)]
