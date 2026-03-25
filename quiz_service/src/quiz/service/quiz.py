from __future__ import annotations

import uuid

from shared.exceptions import NotFoundException
from src.uow import IUnitOfWork
from src.quiz.dto import (
    CreateQuestionDTO,
    CreateQuizDTO,
    QuizDetailResponseDTO,
    QuizListResponseDTO,
)
from src.quiz.entities import QuestionEntity, QuizEntity
from src.quiz.enum import QuestionType

from src.quiz.dependencies.localization import IQuizLocalizationService


class QuizService:
    """Application service orchestrating Quiz domain workflows.

    Coordinates transactional operations via the Unit of Work and delegates
    presentation mapping to the localization service. Provides a complete CMS
    interface for managing quiz content at scale.
    """

    def __init__(
        self,
        uow: IUnitOfWork,
        localization_service: IQuizLocalizationService,
    ) -> None:
        """Initializes the service with required contextual dependencies.

        Args:
            uow: The transactional Unit of Work interface.
            localization_service: The domain service for presentation mapping.
        """
        self._uow = uow
        self._localization = localization_service

    async def get_catalogue(
        self, locale: str, limit: int = 50, offset: int = 0
    ) -> QuizListResponseDTO:
        """Retrieves a paginated, localized catalogue of active quizzes.

        Args:
            locale: The requested ISO language code.
            limit: The maximum number of records to return.
            offset: The number of records to skip.

        Returns:
            A localized QuizListResponseDTO containing summary items and metadata.
        """
        async with self._uow:
            total = await self._uow.quizzes.count_active()
            entities = await self._uow.quizzes.get_all_active(limit=limit, offset=offset)

        items = [self._localization.to_quiz_list_item_dto(q, locale) for q in entities]

        return QuizListResponseDTO(
            items=items,
            total=total,
            page=(offset // limit) + 1 if limit > 0 else 1,
            page_size=limit,
        )

    async def get_quiz_for_attempt(
        self, quiz_id: uuid.UUID, locale: str
    ) -> QuizDetailResponseDTO:
        """Retrieves and strictly sanitizes a quiz for a public-facing user attempt.

        Args:
            quiz_id: The UUID of the requested quiz.
            locale: The requested ISO language code.

        Returns:
            A localized QuizDetailResponseDTO strictly stripped of all grading data.

        Raises:
            NotFoundException: If the quiz does not exist or is inactive.
        """
        async with self._uow:
            quiz = await self._uow.quizzes.get_by_id(quiz_id)

            if not quiz or not quiz.is_active:
                raise NotFoundException(f"Quiz {quiz_id} is not found or currently inactive.")

            return self._localization.to_quiz_detail_dto(quiz, locale)

    async def create_quiz(self, dto: CreateQuizDTO) -> uuid.UUID:
        """Creates a new inactive quiz structure from an administrative DTO.

        Args:
            dto: The comprehensive payload containing localized titles and optional questions.

        Returns:
            The generated UUID of the newly created quiz.
        """
        new_quiz_id = uuid.uuid4()

        quiz_entity = QuizEntity(
            id=new_quiz_id,
            title=dto.title,
            description=dto.description,
            is_active=False,
            questions=[],
        )

        async with self._uow:
            await self._uow.quizzes.add(quiz_entity)

            for index, q_dto in enumerate(dto.questions):
                q_entity = QuestionEntity(
                    id=uuid.uuid4(),
                    type=QuestionType(q_dto.type),
                    order_index=index,
                    text=q_dto.text,
                    payload=q_dto.payload,
                )
                await self._uow.questions.add(q_entity, new_quiz_id)

            await self._uow.commit()

        return new_quiz_id

    async def set_quiz_active_status(self, quiz_id: uuid.UUID, is_active: bool) -> None:
        """Atomically updates the visibility status of a quiz.

        Args:
            quiz_id: The UUID of the target quiz.
            is_active: The boolean visibility state to apply.

        Raises:
            NotFoundException: If the target quiz does not exist.
        """
        async with self._uow:
            updated = await self._uow.quizzes.set_active_status(quiz_id, is_active)
            if not updated:
                raise NotFoundException(f"Quiz {quiz_id} does not exist.")
            await self._uow.commit()

    async def append_question(self, quiz_id: uuid.UUID, dto: CreateQuestionDTO) -> uuid.UUID:
        """Appends a new question to an existing quiz.

        Args:
            quiz_id: The UUID of the target parent quiz.
            dto: The configuration payload for the new question.

        Returns:
            The generated UUID of the newly created question.

        Raises:
            NotFoundException: If the parent quiz does not exist.
        """
        new_question_id = uuid.uuid4()

        async with self._uow:
            quiz = await self._uow.quizzes.get_by_id(quiz_id)
            if not quiz:
                raise NotFoundException(f"Quiz {quiz_id} does not exist.")

            next_index = len(quiz.questions)

            q_entity = QuestionEntity(
                id=new_question_id,
                type=QuestionType(dto.type),
                order_index=next_index,
                text=dto.text,
                payload=dto.payload,
            )

            await self._uow.questions.add(q_entity, quiz_id)
            await self._uow.commit()

        return new_question_id

    async def update_question(
        self, question_id: uuid.UUID, dto: CreateQuestionDTO
    ) -> None:
        """Overwrites the configuration of an existing question.

        Args:
            question_id: The UUID of the target question.
            dto: The updated configuration payload.

        Raises:
            NotFoundException: If the target question does not exist.
        """
        async with self._uow:
            question = await self._uow.questions.get_by_id(question_id)
            if not question:
                raise NotFoundException(f"Question {question_id} does not exist.")

            question.type = QuestionType(dto.type)
            question.text = dto.text
            question.payload = dto.payload

            await self._uow.questions.update(question)
            await self._uow.commit()

    async def delete_question(self, question_id: uuid.UUID) -> None:
        """Hard deletes a question from the system.

        Args:
            question_id: The UUID of the question to remove.

        Raises:
            NotFoundException: If the target question does not exist.
        """
        async with self._uow:
            deleted = await self._uow.questions.delete(question_id)
            if not deleted:
                raise NotFoundException(f"Question {question_id} does not exist.")
            await self._uow.commit()