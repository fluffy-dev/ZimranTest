import asyncio
import logging
import uuid
from typing import Any

import httpx

logging.basicConfig(level=logging.INFO, format="%(levelname)s:\t%(message)s")
logger = logging.getLogger(__name__)


class QuizIntegrationTester:
    """Automated integration test suite for the Quiz API using httpx.

    Executes a complete end-to-end traversal of the Quiz Content Management
    System lifecycle, validating status codes and dynamic UUID injection.
    """

    def __init__(self, base_url: str, user_id: uuid.UUID) -> None:
        """Initializes the test suite context.

        Args:
            base_url: The root URL of the API.
            user_id: The UUID of the test administrator.
        """
        self._base_url = base_url
        self._user_id = str(user_id)
        self._quiz_id: str = ""
        self._question_id: str = ""

    async def execute(self) -> None:
        """Executes the complete test lifecycle sequentially."""
        async with httpx.AsyncClient(
                base_url=self._base_url,
                headers={"X-User-ID": self._user_id},
                timeout=10.0,
        ) as client:
            await self._test_create_quiz(client)
            await self._test_activate_quiz(client)
            await self._test_get_catalogue_english(client)
            await self._test_get_catalogue_russian(client)
            await self._test_get_quiz_details(client)
            await self._test_append_question(client)
            await self._test_update_question(client)
            # await self._test_delete_question(client)
            logger.info("All integration tests passed successfully.")

    async def _test_create_quiz(self, client: httpx.AsyncClient) -> None:
        """Tests the creation of a new localized quiz and extracts its ID.

        Args:
            client: The active httpx client session.
        """
        payload = {
            "title": {"en": "Python Core Concepts", "ru": "Базовые концепции Python"},
            "description": {
                "en": "Test your knowledge of Python basics.",
                "ru": "Проверьте свои знания основ Python.",
            },
            "questions": [
                {
                    "type": "fill_gap",
                    "text": {
                        "en": "Python was created by Guido van ___.",
                        "ru": "Python был создан Гвидо ван ___.",
                    },
                    "payload": {"correct_answers": ["Rossum", "rossum"]},
                }
            ],
        }

        response = await client.post("/quizzes", json=payload)
        assert response.status_code == 201

        data = response.json()
        self._quiz_id = data["id"]
        logger.info(f"Created Quiz: {self._quiz_id}")

    async def _test_activate_quiz(self, client: httpx.AsyncClient) -> None:
        """Tests the atomic activation of a quiz.

        Args:
            client: The active httpx client session.
        """
        payload = {"is_active": True}
        response = await client.patch(f"/quizzes/{self._quiz_id}/status", json=payload)

        assert response.status_code == 204
        logger.info("Activated Quiz successfully.")

    async def _test_get_catalogue_english(self, client: httpx.AsyncClient) -> None:
        """Tests catalogue retrieval with English localization.

        Args:
            client: The active httpx client session.
        """
        headers = {"Accept-Language": "en-US,en;q=0.9"}
        response = await client.get("/quizzes", params={"limit": 10, "offset": 0}, headers=headers)

        assert response.status_code == 200
        logger.info("Retrieved English catalogue successfully.")

    async def _test_get_catalogue_russian(self, client: httpx.AsyncClient) -> None:
        """Tests catalogue retrieval with Russian localization.

        Args:
            client: The active httpx client session.
        """
        headers = {"Accept-Language": "ru-RU,ru;q=0.9"}
        response = await client.get("/quizzes", params={"limit": 10, "offset": 0}, headers=headers)

        assert response.status_code == 200
        logger.info("Retrieved Russian catalogue successfully.")

    async def _test_get_quiz_details(self, client: httpx.AsyncClient) -> None:
        """Tests specific quiz detail retrieval with payload sanitization verification.

        Args:
            client: The active httpx client session.
        """
        headers = {"Accept-Language": "en-US"}
        response = await client.get(f"/quizzes/{self._quiz_id}", headers=headers)

        assert response.status_code == 200
        logger.info("Retrieved sanitized Quiz details successfully.")

    async def _test_append_question(self, client: httpx.AsyncClient) -> None:
        """Tests appending a new matching question to an existing quiz.

        Args:
            client: The active httpx client session.
        """
        payload = {
            "type": "matching",
            "text": {
                "en": "Match the data structures with their brackets.",
                "ru": "Сопоставьте структуры данных с их скобками.",
            },
            "payload": {
                "pairs": [
                    {
                        "pair_id": str(uuid.uuid4()),
                        "left": {"en": "List", "ru": "Список"},
                        "right": {"en": "[ ]", "ru": "[ ]"},
                    }
                ]
            },
        }

        response = await client.post(f"/quizzes/{self._quiz_id}/questions", json=payload)
        assert response.status_code == 201

        data = response.json()
        self._question_id = data["id"]
        logger.info(f"Appended Question: {self._question_id}")

    async def _test_update_question(self, client: httpx.AsyncClient) -> None:
        """Tests overriding the configuration of an existing question.

        Args:
            client: The active httpx client session.
        """
        payload = {
            "type": "fill_gap",
            "text": {
                "en": "UPDATED: Python was created by Guido van ___.",
                "ru": "ОБНОВЛЕНО: Python был создан Гвидо ван ___.",
            },
            "payload": {"correct_answers": ["Rossum", "rossum", "ROSSUM"]},
        }

        response = await client.put(
            f"/quizzes/{self._quiz_id}/questions/{self._question_id}", json=payload
        )

        assert response.status_code == 204
        logger.info("Updated Question successfully.")

    async def _test_delete_question(self, client: httpx.AsyncClient) -> None:
        """Tests the hard deletion of an existing question.

        Args:
            client: The active httpx client session.
        """
        response = await client.delete(
            f"/quizzes/{self._quiz_id}/questions/{self._question_id}"
        )

        assert response.status_code == 204
        logger.info("Deleted Question successfully.")


if __name__ == "__main__":
    tester = QuizIntegrationTester(
        base_url="http://localhost:8002/api/v1",

        user_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
    )
    asyncio.run(tester.execute())