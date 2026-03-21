from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.database.engine import db_helper
from src.attempt.repositories.attempt import AttemptRepository
from src.attempt.repositories.outbox import OutboxRepository

def _get_attempt_repository(session: AsyncSession = Depends(db_helper.get_session)) -> AttemptRepository:
    return AttemptRepository(session)

def _get_outbox_repository(session: AsyncSession = Depends(db_helper.get_session)) -> OutboxRepository:
    return OutboxRepository(session)

IAttemptRepository = Annotated[AttemptRepository, Depends(_get_attempt_repository)]
IOutboxRepository = Annotated[OutboxRepository, Depends(_get_outbox_repository)]
