from typing import Annotated
from fastapi import Depends
from src.quiz.service.quiz import QuizService

IQuizService = Annotated[QuizService, Depends()]
