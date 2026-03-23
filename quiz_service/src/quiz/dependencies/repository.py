from typing import Annotated
from fastapi import Depends
from src.config.database.session import ISession
from src.quiz.repositories.quiz import QuizRepository

IQuizRepository: type[QuizRepository] = Annotated[QuizRepository, Depends()]
