from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.database.engine import db_helper
from src.quiz.repositories.quiz import QuizRepository

# We explicitly inject the database session here so the repository gets initialized
def _get_quiz_repository(session: AsyncSession = Depends(db_helper.get_session)) -> QuizRepository:
    return QuizRepository(session)

IQuizRepository = Annotated[QuizRepository, Depends(_get_quiz_repository)]
