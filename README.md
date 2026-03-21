# Finelo — Quiz & Balance Microservices

Enterprise-grade financial education platform microservices.  
Built with **FastAPI**, **PostgreSQL**, **Redis**, **RabbitMQ**, and **Alembic**.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                          CLIENT / API GATEWAY                        │
│               X-User-ID header (auth handled upstream)              │
└───────────────┬──────────────────────────┬──────────────────────────┘
                │                          │
                ▼                          ▼
   ┌──────────────────────┐    ┌──────────────────────┐
   │    QUIZ SERVICE       │    │   BALANCE SERVICE     │
   │    :8000             │    │   :8001               │
   │                      │    │                       │
   │  ┌────────────────┐  │    │  ┌────────────────┐  │
   │  │ Routers (thin) │  │    │  │ Routers (thin) │  │
   │  └───────┬────────┘  │    │  └───────┬────────┘  │
   │          ▼           │    │          ▼            │
   │  ┌────────────────┐  │    │  ┌────────────────┐  │
   │  │ Service Layer  │  │    │  │ Service Layer  │  │
   │  └───────┬────────┘  │    │  └───────┬────────┘  │
   │          ▼           │    │          ▼            │
   │  ┌────────────────┐  │    │  ┌────────────────┐  │
   │  │  Repositories  │  │    │  │  Repositories  │  │
   │  └───────┬────────┘  │    │  └───────┬────────┘  │
   │          ▼           │    │          ▼            │
   │  ┌──────────────┐    │    │  ┌──────────────┐    │
   │  │  PostgreSQL  │    │    │  │  PostgreSQL  │    │
   │  │  (quiz_db)   │    │    │  │ (balance_db) │    │
   │  └──────────────┘    │    │  └──────────────┘    │
   │  ┌──────────────┐    │    │                       │
   │  │    Redis     │    │    │  ┌────────────────┐  │
   │  └──────────────┘    │    │  │  RabbitMQ      │  │
   │  ┌──────────────┐    │    │  │  Consumer      │  │
   │  │ Outbox Poller│────┼────►  └────────────────┘  │
   │  └──────────────┘AMQP│    └──────────────────────┘
   └──────────────────────┘
```

### Key Design Decisions

| Decision | Implementation |
|---|---|
| **Localization** | JSONB columns `{"en": "...", "de": "...", "tr": "..."}` |
| **Question types** | Enum + JSONB `payload` — polymorphic without extra tables |
| **Reward idempotency** | `(user_id, question_id)` composite PK in `user_rewarded_questions` |
| **Event delivery** | Transactional Outbox — DB write + event in same PG transaction |
| **Balance idempotency** | `idempotency_key = event_id`, UNIQUE on `balance_transactions` |
| **Dead letter** | Failed messages → `balance.quiz_reward.dlq` after nack |

---

## Quick Start

```bash
cp quiz_service/.env.example quiz_service/.env
cp balance_service/.env.example balance_service/.env

docker compose up --build
```

- **Quiz Service:** http://localhost:8000/api/docs
- **Balance Service:** http://localhost:8001/api/docs
- **RabbitMQ UI:** http://localhost:15672 (guest/guest)

### Run Tests

```bash
pip install -e shared/
pip install -e "quiz_service[dev]"
pip install -e "balance_service[dev]"

cd quiz_service && pytest -v
cd balance_service && pytest -v
```

---

## API Reference

### Quiz Service (`:8000`)

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/quizzes` | List quizzes (`Accept-Language` header) |
| `GET` | `/api/v1/quizzes/{id}` | Get quiz (localized, answers hidden) |
| `POST` | `/api/v1/quizzes` | Create quiz |
| `POST` | `/api/v1/quizzes/{id}/attempts` | Start attempt |
| `POST` | `/api/v1/attempts/{id}/submit` | Submit & grade |
| `GET` | `/api/v1/attempts/{id}/result` | Get result |

### Balance Service (`:8001`)

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/balance` | Get balance (`X-User-ID` header) |
| `GET` | `/api/v1/balance/transactions` | History (paginated) |

---

## Question Types

| Type | Payload key | Answer key |
|---|---|---|
| `single_choice` | `correct_id` | `selected_id` |
| `fill_gap` | `correct_answers: [str]` | `answer: str` |
| `multiple_choice` | `correct_ids: [str]` | `selected_ids: [str]` |
| `matching` | `pairs: [{id, left, right}]` | `pairs: [{pair_id, matched_pair_id}]` |

## Supported Languages

`en` `de` `tr` `fr` `it` `id` `tl` (Philippine) + extensible via JSONB
