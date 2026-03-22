from typing import Annotated
from fastapi import Depends
from src.config.database.session import ISession
from src.quiz.repositories.quiz import QuizRepository

def _get_quiz_repository(session: ISession) -> QuizRepository:
    return QuizRepository(session)

IQuizRepository = Annotated[QuizRepository, Depends(_get_quiz_repository)]
