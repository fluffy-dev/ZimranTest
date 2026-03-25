from fastapi import Depends
from typing import Annotated

from src.quiz.service.localization import QuizLocalizationService

IQuizLocalizationService: type[QuizLocalizationService] = Annotated[QuizLocalizationService, Depends()]