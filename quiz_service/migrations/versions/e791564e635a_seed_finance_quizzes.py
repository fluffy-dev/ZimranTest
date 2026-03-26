"""seed_finance_quizzes

Revision ID: e791564e635a
Revises: be4f1928a274
Create Date: 2026-03-26 12:29:34.207818

"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e791564e635a'
down_revision: Union[str, Sequence[str], None] = 'be4f1928a274'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Define table representations for the insert
    quizzes_table = sa.table(
        'quizzes',
        sa.column('id', sa.UUID(as_uuid=True)),
        sa.column('title', postgresql.JSONB),
        sa.column('description', postgresql.JSONB),
        sa.column('is_active', sa.Boolean)
    )

    questions_table = sa.table(
        'questions',
        sa.column('id', sa.UUID(as_uuid=True)),
        sa.column('quiz_id', sa.UUID(as_uuid=True)),
        sa.column('type', sa.String),
        sa.column('order_index', sa.Integer),
        sa.column('text', postgresql.JSONB),
        sa.column('payload', postgresql.JSONB)
    )

    # 2. Generate UUIDs for Quizzes
    quiz_1_id = uuid.uuid4()
    quiz_2_id = uuid.uuid4()
    quiz_3_id = uuid.uuid4()

    # 3. Seed Quizzes
    op.bulk_insert(quizzes_table, [
        {
            "id": quiz_1_id,
            "title": {"en": "Basics of Investing", "ru": "Основы инвестирования", "ge": "Grundlagen des Investierens"},
            "description": {"en": "Core concepts of the stock market.", "ru": "Основные концепции фондового рынка.",
                            "ge": "Grundkonzepte des Aktienmarktes."},
            "is_active": True
        },
        {
            "id": quiz_2_id,
            "title": {"en": "Personal Finance", "ru": "Личные финансы", "ge": "Persönliche Finanzen"},
            "description": {"en": "Test your knowledge on managing money.",
                            "ru": "Проверьте свои знания в управлении деньгами.",
                            "ge": "Testen Sie Ihr Wissen über Geldmanagement."},
            "is_active": True
        },
        {
            "id": quiz_3_id,
            "title": {"en": "Advanced Investments", "ru": "Продвинутые инвестиции",
                      "ge": "Fortgeschrittene Investitionen"},
            "description": {"en": "Deep dive into financial instruments.",
                            "ru": "Глубокое погружение в финансовые инструменты.",
                            "ge": "Tiefer Einblick in Finanzinstrumente."},
            "is_active": True
        }
    ])

    # 4. Seed Questions
    questions_data = [
        # --- QUIZ 1: Basics of Investing ---
        {
            "id": uuid.uuid4(), "quiz_id": quiz_1_id, "type": "multiple_choice", "order_index": 1,
            "text": {"en": "What represents ownership in a company?",
                     "ru": "Что представляет собой доля собственности в компании?",
                     "ge": "Was repräsentiert das Eigentum an einem Unternehmen?"},
            "payload": {
                "options": [{"en": "A Bond", "ru": "Облигация", "ge": "Eine Anleihe"},
                            {"en": "A Stock", "ru": "Акция", "ge": "Eine Aktie"},
                            {"en": "Cash", "ru": "Наличные", "ge": "Bargeld"}],
                "correct_index": 1
            }
        },
        {
            "id": uuid.uuid4(), "quiz_id": quiz_1_id, "type": "multiple_choice", "order_index": 2,
            "text": {"en": "What characterizes a 'bull market'?", "ru": "Что характеризует 'бычий рынок'?",
                     "ge": "Was kennzeichnet einen 'Bullenmarkt'?"},
            "payload": {
                "options": [{"en": "Rising prices", "ru": "Растущие цены", "ge": "Steigende Preise"},
                            {"en": "Falling prices", "ru": "Падающие цены", "ge": "Fallende Preise"},
                            {"en": "Stagnant prices", "ru": "Стагнирующие цены", "ge": "Stagnierende Preise"}],
                "correct_index": 0
            }
        },
        {
            "id": uuid.uuid4(), "quiz_id": quiz_1_id, "type": "true_false", "order_index": 3,
            "text": {"en": "Diversification generally increases your investment risk.",
                     "ru": "Диверсификация обычно увеличивает ваш инвестиционный риск.",
                     "ge": "Diversifikation erhöht im Allgemeinen Ihr Anlagerisiko."},
            "payload": {"correct_answer": False}
        },
        {
            "id": uuid.uuid4(), "quiz_id": quiz_1_id, "type": "multiple_choice", "order_index": 4,
            "text": {"en": "What does ROI stand for?", "ru": "Что означает ROI?", "ge": "Wofür steht ROI?"},
            "payload": {
                "options": [{"en": "Rate of Inflation", "ru": "Уровень инфляции", "ge": "Inflationsrate"},
                            {"en": "Return on Investment", "ru": "Окупаемость инвестиций", "ge": "Kapitalrendite"},
                            {"en": "Risk of Interest", "ru": "Риск процентов", "ge": "Zinsrisiko"}],
                "correct_index": 1
            }
        },
        {
            "id": uuid.uuid4(), "quiz_id": quiz_1_id, "type": "true_false", "order_index": 5,
            "text": {"en": "A bond is essentially a loan you make to a company or government.",
                     "ru": "Облигация — это, по сути, кредит, который вы даете компании или правительству.",
                     "ge": "Eine Anleihe ist im Wesentlichen ein Darlehen, das Sie einem Unternehmen oder einer Regierung gewähren."},
            "payload": {"correct_answer": True}
        },

        # --- QUIZ 2: Personal Finance ---
        {
            "id": uuid.uuid4(), "quiz_id": quiz_2_id, "type": "multiple_choice", "order_index": 1,
            "text": {"en": "What is the primary purpose of an emergency fund?",
                     "ru": "Какова основная цель резервного фонда?",
                     "ge": "Was ist der Hauptzweck eines Notgroschens?"},
            "payload": {
                "options": [
                    {"en": "Buying luxury goods", "ru": "Покупка предметов роскоши", "ge": "Kauf von Luxusgütern"},
                    {"en": "Investing in crypto", "ru": "Инвестиции в крипту", "ge": "Investieren in Krypto"},
                    {"en": "Covering unexpected expenses", "ru": "Покрытие непредвиденных расходов",
                     "ge": "Deckung unerwarteter Ausgaben"}],
                "correct_index": 2
            }
        },
        {
            "id": uuid.uuid4(), "quiz_id": quiz_2_id, "type": "multiple_choice", "order_index": 2,
            "text": {"en": "The 50/30/20 budgeting rule suggests allocating 20% to...",
                     "ru": "Правило бюджета 50/30/20 предлагает выделять 20% на...",
                     "ge": "Die 50/30/20-Budgetierungsregel schlägt vor, 20% zuzuweisen für..."},
            "payload": {
                "options": [{"en": "Wants", "ru": "Желания", "ge": "Wünsche"},
                            {"en": "Savings and Debt", "ru": "Сбережения и долги", "ge": "Ersparnisse und Schulden"},
                            {"en": "Needs", "ru": "Потребности", "ge": "Bedürfnisse"}],
                "correct_index": 1
            }
        },
        {
            "id": uuid.uuid4(), "quiz_id": quiz_2_id, "type": "true_false", "order_index": 3,
            "text": {"en": "Inflation decreases your purchasing power over time.",
                     "ru": "Инфляция со временем снижает вашу покупательную способность.",
                     "ge": "Inflation verringert Ihre Kaufkraft im Laufe der Zeit."},
            "payload": {"correct_answer": True}
        },
        {
            "id": uuid.uuid4(), "quiz_id": quiz_2_id, "type": "multiple_choice", "order_index": 4,
            "text": {"en": "What does a credit score evaluate?", "ru": "Что оценивает кредитный рейтинг?",
                     "ge": "Was bewertet eine Kreditwürdigkeit?"},
            "payload": {
                "options": [{"en": "Your total net worth", "ru": "Ваш общий капитал", "ge": "Ihr Gesamtvermögen"},
                            {"en": "Your borrowing risk", "ru": "Ваш риск как заемщика", "ge": "Ihr Kreditrisiko"},
                            {"en": "Your annual salary", "ru": "Вашу годовую зарплату", "ge": "Ihr Jahresgehalt"}],
                "correct_index": 1
            }
        },
        {
            "id": uuid.uuid4(), "quiz_id": quiz_2_id, "type": "true_false", "order_index": 5,
            "text": {"en": "Compound interest applies only to the initial principal, not accumulated interest.",
                     "ru": "Сложный процент применяется только к первоначальной сумме, а не к накопленным процентам.",
                     "ge": "Zinseszins gilt nur für das ursprüngliche Kapital, nicht für angesammelte Zinsen."},
            "payload": {"correct_answer": False}
        },

        # --- QUIZ 3: Advanced Investments ---
        {
            "id": uuid.uuid4(), "quiz_id": quiz_3_id, "type": "multiple_choice", "order_index": 1,
            "text": {"en": "What is an ETF?", "ru": "Что такое ETF?", "ge": "Was ist ein ETF?"},
            "payload": {
                "options": [{"en": "Equity Trading Facility", "ru": "Механизм торговли акциями",
                             "ge": "Aktienhandelsfazilität"},
                            {"en": "Exchange-Traded Fund", "ru": "Биржевой инвестиционный фонд",
                             "ge": "Börsengehandelter Fonds"},
                            {"en": "Extra Tax Fee", "ru": "Дополнительный налоговый сбор",
                             "ge": "Zusätzliche Steuergebühr"}],
                "correct_index": 1
            }
        },
        {
            "id": uuid.uuid4(), "quiz_id": quiz_3_id, "type": "multiple_choice", "order_index": 2,
            "text": {"en": "What does 'short selling' mean?", "ru": "Что означает 'короткая продажа' (шорт)?",
                     "ge": "Was bedeutet 'Leerverkauf'?"},
            "payload": {
                "options": [{"en": "Betting an asset's price will fall", "ru": "Ставка на падение цены актива",
                             "ge": "Wetten, dass der Preis eines Vermögenswerts fällt"},
                            {"en": "Selling assets very quickly", "ru": "Очень быстрая продажа активов",
                             "ge": "Sehr schneller Verkauf von Vermögenswerten"},
                            {"en": "Selling fractional shares", "ru": "Продажа дробных акций",
                             "ge": "Verkauf von Teilaktien"}],
                "correct_index": 0
            }
        },
        {
            "id": uuid.uuid4(), "quiz_id": quiz_3_id, "type": "true_false", "order_index": 3,
            "text": {"en": "High liquidity means an asset is difficult to sell quickly without losing value.",
                     "ru": "Высокая ликвидность означает, что актив трудно продать быстро без потери стоимости.",
                     "ge": "Eine hohe Liquidität bedeutet, dass ein Vermögenswert schwer schnell ohne Wertverlust zu verkaufen ist."},
            "payload": {"correct_answer": False}
        },
        {
            "id": uuid.uuid4(), "quiz_id": quiz_3_id, "type": "multiple_choice", "order_index": 4,
            "text": {"en": "What is a dividend?", "ru": "Что такое дивиденд?", "ge": "Was ist eine Dividende?"},
            "payload": {
                "options": [
                    {"en": "A tax on investments", "ru": "Налог на инвестиции", "ge": "Eine Steuer auf Investitionen"},
                    {"en": "A portion of company profits paid to shareholders",
                     "ru": "Часть прибыли компании, выплачиваемая акционерам",
                     "ge": "Ein Teil des Unternehmensgewinns, der an die Aktionäre ausgeschüttet wird"},
                    {"en": "A fee to brokers", "ru": "Комиссия брокерам", "ge": "Eine Gebühr an Makler"}],
                "correct_index": 1
            }
        },
        {
            "id": uuid.uuid4(), "quiz_id": quiz_3_id, "type": "multiple_choice", "order_index": 5,
            "text": {"en": "How is a company's Market Capitalization calculated?",
                     "ru": "Как рассчитывается рыночная капитализация компании?",
                     "ge": "Wie wird die Marktkapitalisierung eines Unternehmens berechnet?"},
            "payload": {
                "options": [
                    {"en": "Total assets minus total liabilities", "ru": "Общие активы минус общие обязательства",
                     "ge": "Gesamtvermögen abzüglich Gesamtverbindlichkeiten"},
                    {"en": "Share price multiplied by total number of shares",
                     "ru": "Цена акции, умноженная на общее количество акций",
                     "ge": "Aktienkurs multipliziert mit der Gesamtzahl der Aktien"},
                    {"en": "Annual revenue divided by profit", "ru": "Годовой доход, разделенный на прибыль",
                     "ge": "Jahresumsatz geteilt durch Gewinn"}],
                "correct_index": 1
            }
        }
    ]

    op.bulk_insert(questions_table, questions_data)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DELETE FROM questions")
    op.execute("DELETE FROM quizzes")
