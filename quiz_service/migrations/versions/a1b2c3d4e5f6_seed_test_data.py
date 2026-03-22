"""seed test data

Revision ID: a1b2c3d4e5f6
Revises: 20be996f9a32
Create Date: 2026-03-22 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "20be996f9a32"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

QUIZ_1_ID = "11111111-1111-1111-1111-111111111111"
QUIZ_2_ID = "22222222-2222-2222-2222-222222222222"

Q1_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
Q2_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
Q3_ID = "cccccccc-cccc-cccc-cccc-cccccccccccc"
Q4_ID = "dddddddd-dddd-dddd-dddd-dddddddddddd"
Q5_ID = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"
Q6_ID = "ffffffff-ffff-ffff-ffff-ffffffffffff"


def upgrade() -> None:
    """Insert sample quizzes and questions for testing."""

    # Quiz 1: Crypto Basics (all 4 question types)
    op.execute(f"""
        INSERT INTO quizzes (id, title, description, is_active)
        VALUES (
            '{QUIZ_1_ID}',
            '{{"en": "Crypto Basics", "de": "Krypto-Grundlagen", "tr": "Kripto Temelleri"}}',
            '{{"en": "Test your knowledge of cryptocurrency fundamentals.", "de": "Testen Sie Ihr Wissen ueber Kryptowaehrungen.", "tr": "Kripto para temellerini test edin."}}',
            true
        )
    """)

    # Q1: Single Choice
    op.execute(f"""
        INSERT INTO questions (id, quiz_id, type, order_index, text, payload)
        VALUES (
            '{Q1_ID}', '{QUIZ_1_ID}', 'single_choice', 0,
            '{{"en": "What is Bitcoin?", "de": "Was ist Bitcoin?", "tr": "Bitcoin nedir?"}}',
            '{{"options": [{{"id": "a", "text": {{"en": "A cryptocurrency", "de": "Eine Kryptowaehrung", "tr": "Bir kripto para"}}}}, {{"id": "b", "text": {{"en": "A bank", "de": "Eine Bank", "tr": "Bir banka"}}}}, {{"id": "c", "text": {{"en": "A stock", "de": "Eine Aktie", "tr": "Bir hisse"}}}}], "correct_id": "a"}}'
        )
    """)

    # Q2: Fill the Gap
    op.execute(f"""
        INSERT INTO questions (id, quiz_id, type, order_index, text, payload)
        VALUES (
            '{Q2_ID}', '{QUIZ_1_ID}', 'fill_gap', 1,
            '{{"en": "The creator of Bitcoin is known as ___", "de": "Der Schoepfer von Bitcoin ist bekannt als ___", "tr": "Bitcoin in yaraticisi ___ olarak bilinir"}}',
            '{{"correct_answers": ["Satoshi Nakamoto", "Satoshi", "Nakamoto"]}}'
        )
    """)

    # Q3: Multiple Choice
    op.execute(f"""
        INSERT INTO questions (id, quiz_id, type, order_index, text, payload)
        VALUES (
            '{Q3_ID}', '{QUIZ_1_ID}', 'multiple_choice', 2,
            '{{"en": "Which are cryptocurrencies?", "de": "Welche sind Kryptowaehrungen?", "tr": "Hangileri kripto paradir?"}}',
            '{{"options": [{{"id": "a", "text": {{"en": "Bitcoin"}}}}, {{"id": "b", "text": {{"en": "Ethereum"}}}}, {{"id": "c", "text": {{"en": "USD"}}}}, {{"id": "d", "text": {{"en": "Solana"}}}}], "correct_ids": ["a", "b", "d"]}}'
        )
    """)

    # Q4: Matching
    op.execute(f"""
        INSERT INTO questions (id, quiz_id, type, order_index, text, payload)
        VALUES (
            '{Q4_ID}', '{QUIZ_1_ID}', 'matching', 3,
            '{{"en": "Match the crypto to its ticker", "de": "Ordnen Sie die Kryptowaehrung ihrem Ticker zu", "tr": "Kripto parayi tickerina esleyin"}}',
            '{{"pairs": [{{"id": "p1", "left": {{"en": "Bitcoin"}}, "right": {{"en": "BTC"}}}}, {{"id": "p2", "left": {{"en": "Ethereum"}}, "right": {{"en": "ETH"}}}}]}}'
        )
    """)

    # Quiz 2: Investment Basics (2 fill_gap questions)
    op.execute(f"""
        INSERT INTO quizzes (id, title, description, is_active)
        VALUES (
            '{QUIZ_2_ID}',
            '{{"en": "Investment 101", "de": "Investieren 101", "tr": "Yatirim 101"}}',
            '{{"en": "Learn the basics of investing.", "de": "Lernen Sie die Grundlagen des Investierens.", "tr": "Yatirim temellerini ogrenin."}}',
            true
        )
    """)

    op.execute(f"""
        INSERT INTO questions (id, quiz_id, type, order_index, text, payload)
        VALUES (
            '{Q5_ID}', '{QUIZ_2_ID}', 'fill_gap', 0,
            '{{"en": "An ETF stands for Exchange-Traded ___", "de": "Ein ETF steht fuer Exchange-Traded ___", "tr": "ETF, Borsa Islem Goren ___ anlamina gelir"}}',
            '{{"correct_answers": ["Fund", "fund"]}}'
        )
    """)

    op.execute(f"""
        INSERT INTO questions (id, quiz_id, type, order_index, text, payload)
        VALUES (
            '{Q6_ID}', '{QUIZ_2_ID}', 'fill_gap', 1,
            '{{"en": "Diversification reduces ___", "de": "Diversifikation reduziert ___", "tr": "Cesitlendirme ___ azaltir"}}',
            '{{"correct_answers": ["risk", "Risk"]}}'
        )
    """)


def downgrade() -> None:
    """Remove seed data."""
    op.execute(f"DELETE FROM questions WHERE quiz_id IN ('{QUIZ_1_ID}', '{QUIZ_2_ID}')")
    op.execute(f"DELETE FROM quizzes WHERE id IN ('{QUIZ_1_ID}', '{QUIZ_2_ID}')")
