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
            "title": {"en": "Basics of Investing", "ru": "Основы инвестирования", "de": "Grundlagen des Investierens"},
            "description": {"en": "Core concepts of the stock market.", "ru": "Основные концепции фондового рынка.",
                            "de": "Grundkonzepte des Aktienmarktes."},
            "is_active": True
        },
        {
            "id": quiz_2_id,
            "title": {"en": "Personal Finance", "ru": "Личные финансы", "de": "Persönliche Finanzen"},
            "description": {"en": "Test your knowledge on managing money.",
                            "ru": "Проверьте свои знания в управлении деньгами.",
                            "de": "Testen Sie Ihr Wissen über Geldmanagement."},
            "is_active": True
        },
        {
            "id": quiz_3_id,
            "title": {"en": "Advanced Investments", "ru": "Продвинутые инвестиции",
                      "de": "Fortgeschrittene Investitionen"},
            "description": {"en": "Deep dive into financial instruments.",
                            "ru": "Глубокое погружение в финансовые инструменты.",
                            "de": "Tiefer Einblick in Finanzinstrumente."},
            "is_active": True
        }
    ])

    # 4. Seed Questions
    questions_data = []

    def make_single_choice(q_id, q_quiz_id, q_order, q_text_en, q_text_ru, q_text_de, options_data, correct_idx):
        opts = [
            {"id": str(uuid.uuid4()), "text": {"en": opt["en"], "ru": opt["ru"], "de": opt["de"]}}
            for opt in options_data
        ]
        return {
            "id": q_id,
            "quiz_id": q_quiz_id,
            "type": "SINGLE_CHOICE",
            "order_index": q_order,
            "text": {"en": q_text_en, "ru": q_text_ru, "de": q_text_de},
            "payload": {
                "correct_id": opts[correct_idx]["id"],
                "options": opts
            }
        }

    def make_true_false(q_id, q_quiz_id, q_order, q_text_en, q_text_ru, q_text_de, is_true):
        return make_single_choice(
            q_id, q_quiz_id, q_order, q_text_en, q_text_ru, q_text_de,
            [
                {"en": "True", "ru": "Правильно", "de": "Wahr"},
                {"en": "False", "ru": "Неправильно", "de": "Falsch"}
            ],
            0 if is_true else 1
        )

    questions_data.extend([
        # --- QUIZ 1: Basics of Investing ---
        make_single_choice(
            uuid.uuid4(), quiz_1_id, 1,
            "What represents ownership in a company?",
            "Что представляет собой доля собственности в компании?",
            "Was repräsentiert das Eigentum an einem Unternehmen?",
            [{"en": "A Bond", "ru": "Облигация", "de": "Eine Anleihe"},
             {"en": "A Stock", "ru": "Акция", "de": "Eine Aktie"},
             {"en": "Cash", "ru": "Наличные", "de": "Bargeld"}],
            1
        ),
        make_single_choice(
            uuid.uuid4(), quiz_1_id, 2,
            "What characterizes a 'bull market'?",
            "Что характеризует 'бычий рынок'?",
            "Was kennzeichnet einen 'Bullenmarkt'?",
            [{"en": "Rising prices", "ru": "Растущие цены", "de": "Steigende Preise"},
             {"en": "Falling prices", "ru": "Падающие цены", "de": "Fallende Preise"},
             {"en": "Stagnant prices", "ru": "Стагнирующие цены", "de": "Stagnierende Preise"}],
            0
        ),
        make_true_false(
            uuid.uuid4(), quiz_1_id, 3,
            "Diversification generally increases your investment risk.",
            "Диверсификация обычно увеличивает ваш инвестиционный риск.",
            "Diversifikation erhöht im Allgemeinen Ihr Anlagerisiko.",
            False
        ),
        make_single_choice(
            uuid.uuid4(), quiz_1_id, 4,
            "What does ROI stand for?",
            "Что означает ROI?",
            "Wofür steht ROI?",
            [{"en": "Rate of Inflation", "ru": "Уровень инфляции", "de": "Inflationsrate"},
             {"en": "Return on Investment", "ru": "Окупаемость инвестиций", "de": "Kapitalrendite"},
             {"en": "Risk of Interest", "ru": "Риск процентов", "de": "Zinsrisiko"}],
            1
        ),
        make_true_false(
            uuid.uuid4(), quiz_1_id, 5,
            "A bond is essentially a loan you make to a company or government.",
            "Облигация — это, по сути, кредит, который вы даете компании или правительству.",
            "Eine Anleihe ist im Wesentlichen ein Darlehen, das Sie einem Unternehmen oder einer Regierung gewähren.",
            True
        ),

        # --- QUIZ 2: Personal Finance ---
        make_single_choice(
            uuid.uuid4(), quiz_2_id, 1,
            "What is the primary purpose of an emergency fund?",
            "Какова основная цель резервного фонда?",
            "Was ist der Hauptzweck eines Notgroschens?",
            [{"en": "Buying luxury goods", "ru": "Покупка предметов роскоши", "de": "Kauf von Luxusgütern"},
             {"en": "Investing in crypto", "ru": "Инвестиции в крипту", "de": "Investieren in Krypto"},
             {"en": "Covering unexpected expenses", "ru": "Покрытие непредвиденных расходов", "de": "Deckung unerwarteter Ausgaben"}],
            2
        ),
        make_single_choice(
            uuid.uuid4(), quiz_2_id, 2,
            "The 50/30/20 budgeting rule suggests allocating 20% to...",
            "Правило бюджета 50/30/20 предлагает выделять 20% на...",
            "Die 50/30/20-Budgetierungsregel schlägt vor, 20% zuzuweisen für...",
            [{"en": "Wants", "ru": "Желания", "de": "Wünsche"},
             {"en": "Savings and Debt", "ru": "Сбережения и долги", "de": "Ersparnisse und Schulden"},
             {"en": "Needs", "ru": "Потребности", "de": "Bedürfnisse"}],
            1
        ),
        make_true_false(
            uuid.uuid4(), quiz_2_id, 3,
            "Inflation decreases your purchasing power over time.",
            "Инфляция со временем снижает вашу покупательную способность.",
            "Inflation verringert Ihre Kaufkraft im Laufe der Zeit.",
            True
        ),
        make_single_choice(
            uuid.uuid4(), quiz_2_id, 4,
            "What does a credit score evaluate?",
            "Что оценивает кредитный рейтинг?",
            "Was bewertet eine Kreditwürdigkeit?",
            [{"en": "Your total net worth", "ru": "Ваш общий капитал", "de": "Ihr Gesamtvermögen"},
             {"en": "Your borrowing risk", "ru": "Ваш риск как заемщика", "de": "Ihr Kreditrisiko"},
             {"en": "Your annual salary", "ru": "Вашу годовую зарплату", "de": "Ihr Jahresgehalt"}],
            1
        ),
        make_true_false(
            uuid.uuid4(), quiz_2_id, 5,
            "Compound interest applies only to the initial principal, not accumulated interest.",
            "Сложный процент применяется только к первоначальной сумме, а не к накопленным процентам.",
            "Zinseszins gilt nur für das ursprüngliche Kapital, nicht für angesammelte Zinsen.",
            False
        ),

        # --- QUIZ 3: Advanced Investments ---
        make_single_choice(
            uuid.uuid4(), quiz_3_id, 1,
            "What is an ETF?",
            "Что такое ETF?",
            "Was ist ein ETF?",
            [{"en": "Equity Trading Facility", "ru": "Механизм торговли акциями", "de": "Aktienhandelsfazilität"},
             {"en": "Exchange-Traded Fund", "ru": "Биржевой инвестиционный фонд", "de": "Börsengehandelter Fonds"},
             {"en": "Extra Tax Fee", "ru": "Дополнительный налоговый сбор", "de": "Zusätzliche Steuergebühr"}],
            1
        ),
        make_single_choice(
            uuid.uuid4(), quiz_3_id, 2,
            "What does 'short selling' mean?",
            "Что означает 'короткая продажа' (шорт)?",
            "Was bedeutet 'Leerverkauf'?",
            [{"en": "Betting an asset's price will fall", "ru": "Ставка на падение цены актива", "de": "Wetten, dass der Preis eines Vermögenswerts fällt"},
             {"en": "Selling assets very quickly", "ru": "Очень быстрая продажа активов", "de": "Sehr schneller Verkauf von Vermögenswerten"},
             {"en": "Selling fractional shares", "ru": "Продажа дробных акций", "de": "Verkauf von Teilaktien"}],
            0
        ),
        make_true_false(
            uuid.uuid4(), quiz_3_id, 3,
            "High liquidity means an asset is difficult to sell quickly without losing value.",
            "Высокая ликвидность означает, что актив трудно продать быстро без потери стоимости.",
            "Eine hohe Liquidität bedeutet, dass ein Vermögenswert schwer schnell ohne Wertverlust zu verkaufen ist.",
            False
        ),
        make_single_choice(
            uuid.uuid4(), quiz_3_id, 4,
            "What is a dividend?",
            "Что такое дивиденд?",
            "Was ist eine Dividende?",
            [{"en": "A tax on investments", "ru": "Налог на инвестиции", "de": "Eine Steuer auf Investitionen"},
             {"en": "A portion of company profits paid to shareholders", "ru": "Часть прибыли компании, выплачиваемая акционерам", "de": "Ein Teil des Unternehmensgewinns, der an die Aktionäre ausgeschüttet wird"},
             {"en": "A fee to brokers", "ru": "Комиссия брокерам", "de": "Eine Gebühr an Makler"}],
            1
        ),
        make_single_choice(
            uuid.uuid4(), quiz_3_id, 5,
            "How is a company's Market Capitalization calculated?",
            "Как рассчитывается рыночная капитализация компании?",
            "Wie wird die Marktkapitalisierung eines Unternehmens berechnet?",
            [{"en": "Total assets minus total liabilities", "ru": "Общие активы минус общие обязательства", "de": "Gesamtvermögen abzüglich Gesamtverbindlichkeiten"},
             {"en": "Share price multiplied by total number of shares", "ru": "Цена акции, умноженная на общее количество акций", "de": "Aktienkurs multipliziert mit der Gesamtzahl der Aktien"},
             {"en": "Annual revenue divided by profit", "ru": "Годовой доход, разделенный на прибыль", "de": "Jahresumsatz geteilt durch Gewinn"}],
            1
        )
    ])


    op.bulk_insert(questions_table, questions_data)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DELETE FROM questions")
    op.execute("DELETE FROM quizzes")
