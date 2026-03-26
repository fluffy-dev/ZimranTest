# Finelo Quiz and Balance Platform

> Developed by **Rauan Assetov**  
> 🔗 [Repository on GitHub](https://github.com/fluffy-dev/ZimranTest)

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture Overview](#2-architecture-overview)
3. [Repository Structure](#3-repository-structure)
4. [Technology Stack](#4-technology-stack)
5. [Shared Library](#5-shared-library)
6. [Quiz Service](#6-quiz-service)
   - [Domain Model](#61-domain-model)
   - [Database Schema](#62-database-schema)
   - [Question Types](#63-question-types)
   - [Localization Design](#64-localization-design)
   - [Caching Layer](#65-caching-layer)
   - [Transactional Outbox Pattern](#66-transactional-outbox-pattern)
   - [Reward Idempotency](#67-reward-idempotency)
   - [Attempt Lifecycle](#68-attempt-lifecycle)
   - [API Reference](#69-api-reference)
7. [Balance Service](#7-balance-service)
   - [Domain Model](#71-domain-model)
   - [Database Schema](#72-database-schema)
   - [Consumer and Supervisor](#73-consumer-and-supervisor)
   - [Idempotent Credits](#74-idempotent-credits)
   - [API Reference](#75-api-reference)
8. [Service Communication Flow](#8-service-communication-flow)
9. [Infrastructure](#9-infrastructure)
10. [Running the Project](#10-running-the-project)
11. [Environment Variables Reference](#11-environment-variables-reference)
12. [Database Migrations](#12-database-migrations)
13. [Running Tests](#13-running-tests)
14. [Test Coverage Breakdown](#14-test-coverage-breakdown)
15. [Sample Data and Manual API Testing](#15-sample-data-and-manual-api-testing)
16. [Design Decisions and Patterns](#16-design-decisions-and-patterns)
17. [Known Limitations and Future Improvements](#17-known-limitations-and-future-improvements)

---

## 1. Project Overview

This is the backend for the quiz and balance features of **Finelo**, a financial education platform available in nine languages. The system consists of two independently deployable microservices that communicate asynchronously through a message broker.

**Quiz Service** — stores localized quiz content, manages the full lifecycle of user quiz attempts, grades answers, and emits reward events. Supports four question types: single choice, fill-in-the-gap, multiple choice, and matching.

**Balance Service** — maintains a virtual currency ledger, receives reward events, and credits user balances idempotently. Runs its own PostgreSQL database, its own HTTP surface, and its own migration history.

Both services are built with FastAPI using fully asynchronous code, backed by PostgreSQL, and orchestrated together via Docker Compose.

### Key Features

- **Full localization** — quiz titles, descriptions, question texts, and option labels are stored as JSONB locale maps. The platform currently supports nine languages with a three-step locale fallback.
- **Four question types** — single choice, multiple choice, fill-in-the-gap, and matching, each with type-specific grading logic.
- **Idempotent per-question rewarding** — a `user_rewarded_questions` table ensures each user is rewarded only once per correctly answered question, even across multiple attempts.
- **Transactional outbox pattern** — reward events are written to the database in the same transaction as business state changes and then published to RabbitMQ by a background worker, solving the dual-write problem.
- **Automatic balance crediting** — 100 coins per correctly answered question, deduplicated against previously rewarded questions, delivered reliably via the outbox over RabbitMQ.
- **Pessimistic locking** — concurrent attempt submissions are handled with `SELECT ... FOR UPDATE`, preventing race conditions.
- **Auto-save drafts** — users can save draft answers during an active attempt without affecting grading.
- **Structured logging** — JSON-formatted logs with correlation IDs for end-to-end request tracing.
- **Consumer supervisor** — exponential backoff reconnection for the RabbitMQ consumer.
- **Dead-letter queue** — failed messages are routed to a DLQ for inspection and replay.

---

## 2. Architecture Overview

The system follows an event-driven microservices architecture. The two services share no database and do not call each other over HTTP. Communication flows in one direction: the quiz service emits events, and the balance service consumes them.

```
Client (browser / mobile)
      |
      | HTTP   X-User-ID header carries authenticated user UUID
      |
      +----> quiz_service  (port 8002)
      |           |
      |           | PostgreSQL (quiz_db, port 5432)
      |           | Redis (port 6379) -- quiz catalogue cache
      |           |
      |           | Transactional Outbox
      |           | Outbox worker polls outbox_events table
      |           | Publishes to RabbitMQ exchange: finelo.events
      |           | Routing key: quiz.questions.rewarded
      |
      | HTTP
      |
      +----> balance_service  (port 8001)
                  |
                  | PostgreSQL (balance_db, port 5433)
                  |
                  | RabbitMQ consumer
                  | Queue: balance.quiz_reward
                  | Bound to exchange: finelo.events
                  | Routing key: quiz.questions.rewarded
```

The quiz service exposes two logical groups of endpoints under /api/v1:

- /quizzes for content management (creating quizzes, adding questions, toggling status) and catalogue browsing.
- /attempts for the user-facing quiz attempt lifecycle (starting, auto-saving drafts, submitting, abandoning).

The balance service exposes one logical group of endpoints under /api/v1:

- /balances for reading a user's current balance and paginated transaction history.

Both services additionally expose /health/live and /health/ready for container orchestration.

---

## 3. Repository Structure

```
.
├── docker-compose.yml          -- Orchestrates all services and infrastructure
├── Makefile                    -- Helper targets: up, down, clean, logs, restart
├── LICENSE
│
├── shared/                     -- Installable Python library shared by both services
│   ├── pyproject.toml
│   └── shared/
│       ├── __init__.py
│       ├── exceptions.py       -- Domain exception hierarchy
│       ├── logging.py          -- Structlog configuration
│       ├── schemas.py          -- Cross-service Pydantic event schemas
│       └── messaging/
│           ├── __init__.py
│           ├── base.py         -- MessagePublisher and MessageConsumer protocols
│           ├── rabbitmq.py     -- RabbitMQ publisher and consumer implementations
│           └── kafka.py        -- Kafka publisher and consumer implementations (available)
│
├── quiz_service/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── pytest.ini
│   ├── alembic.ini
│   ├── .env                    -- Local dev environment (see .env.example for reference)
│   ├── .env.example
│   ├── migrations/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   ├── models.py           -- Imports all ORM models for autogenerate
│   │   └── versions/
│   │       └── ...             -- Alembic migration scripts
│   ├── src/
│   │   ├── app.py              -- FastAPI application factory, middleware, exception handlers
│   │   ├── lifespan.py         -- Startup/shutdown: Redis, RabbitMQ, outbox worker
│   │   ├── uow.py              -- Unit of Work interface and SQLAlchemy implementation
│   │   ├── libs/
│   │   │   └── base_model.py   -- SQLAlchemy DeclarativeBase + TimestampMixin
│   │   ├── config/
│   │   │   ├── project.py      -- App-level settings (host, port, version, coin amount)
│   │   │   ├── cors.py         -- CORS settings with comma-delimited list parsing
│   │   │   ├── swagger.py      -- OpenAPI metadata settings
│   │   │   ├── logging.py      -- Logging level settings
│   │   │   ├── redis.py        -- Redis URL and cache TTL
│   │   │   ├── rabbitmq.py     -- RabbitMQ URL, exchange, routing key
│   │   │   ├── outbox.py       -- Outbox poll interval and batch size
│   │   │   └── database/
│   │   │       ├── settings.py -- Database connection DSN assembly
│   │   │       ├── engine.py   -- DatabaseHelper: engine, session factory, scoped sessions
│   │   │       └── session.py  -- ISession FastAPI dependency alias
│   │   ├── dependencies/
│   │   │   └── common.py       -- ISession, IRedis, IUserID, ILocale FastAPI dependencies
│   │   ├── health/
│   │   │   └── router.py       -- /health/live and /health/ready
│   │   ├── quiz/
│   │   │   ├── entities.py     -- QuizEntity, QuestionEntity (dataclasses, no ORM)
│   │   │   ├── enum.py         -- QuestionType enum
│   │   │   ├── dto.py          -- Request and response Pydantic models
│   │   │   ├── router.py       -- Quiz and question CRUD routes
│   │   │   ├── models/
│   │   │   │   ├── quiz.py     -- Quiz SQLAlchemy model
│   │   │   │   └── question.py -- Question SQLAlchemy model
│   │   │   ├── repositories/
│   │   │   │   ├── quiz.py     -- QuizRepository (DB-backed)
│   │   │   │   ├── question.py -- QuestionRepository
│   │   │   │   └── cached_quiz.py -- CachingQuizRepository (Redis wrapper)
│   │   │   ├── service/
│   │   │   │   ├── quiz.py          -- QuizService (CRUD + catalogue orchestration)
│   │   │   │   └── localization.py  -- QuizLocalizationService (text extraction + DTO mapping)
│   │   │   └── dependencies/
│   │   │       ├── service.py
│   │   │       └── localization.py
│   │   └── attempt/
│   │       ├── entities.py     -- QuizAttemptEntity, UserQuestionAnswerEntity, OutboxEventEntity
│   │       ├── enum.py         -- AttemptStatusEnum
│   │       ├── dto.py          -- All attempt DTOs and strict answer payload types
│   │       ├── router.py       -- Attempt lifecycle routes
│   │       ├── models/
│   │       │   ├── quiz_attempt.py          -- QuizAttempt SQLAlchemy model
│   │       │   ├── user_question_answer.py  -- UserQuestionAnswer SQLAlchemy model
│   │       │   ├── user_rewarded_question.py -- UserRewardedQuestion SQLAlchemy model
│   │       │   └── outbox_event.py          -- OutboxEvent SQLAlchemy model
│   │       ├── repositories/
│   │       │   ├── quiz_attempt.py          -- QuizAttemptRepository
│   │       │   ├── user_question_answer.py  -- UserQuestionAnswerRepository
│   │       │   ├── user_rewarded_question.py -- UserRewardedQuestionRepository
│   │       │   └── outbox_event.py          -- OutboxEventRepository
│   │       ├── service/
│   │       │   ├── attempt.py  -- AttemptService (start, auto-save, submit, abandon)
│   │       │   ├── reward.py   -- RewardService (idempotent reward calculation + outbox staging)
│   │       │   └── grading.py  -- GradingService (stateless answer evaluation)
│   │       └── dependencies/
│   │           ├── attempt_service.py
│   │           ├── reward_service.py
│   │           └── grading_service.py
│   └── tests/
│       ├── conftest.py
│       ├── unit/
│       │   ├── test_grading_service.py
│       │   ├── test_attempt_service.py
│       │   └── test_reward_service.py
│       └── integration/
│           ├── test_routes.py
│           └── test_race_condition.py
│
└── balance_service/
    ├── Dockerfile
    ├── pyproject.toml
    ├── pytest.ini
    ├── alembic.ini
    ├── .env
    ├── .env.example
    ├── migrations/
    │   ├── env.py
    │   ├── script.py.mako
    │   ├── models.py
    │   └── versions/
    │       └── 9b6cd6f575ab_add_balance_models.py
    ├── src/
    │   ├── app.py              -- FastAPI application factory
    │   ├── lifespan.py         -- Consumer supervisor with exponential backoff
    │   ├── uow.py              -- AbstractUnitOfWork + SqlAlchemyUnitOfWork
    │   ├── libs/
    │   │   └── base_model.py   -- DeclarativeBase
    │   ├── config/
    │   │   ├── project.py
    │   │   ├── cors.py
    │   │   ├── swagger.py
    │   │   ├── logging.py
    │   │   ├── rabbitmq.py     -- URL, exchange, queue, routing key
    │   │   └── database/
    │   │       ├── settings.py
    │   │       ├── engine.py
    │   │       └── session.py
    │   ├── dependencies/
    │   │   └── common.py       -- IUserID dependency
    │   ├── health/
    │   │   └── router.py
    │   ├── balance/
    │   │   ├── entities.py     -- BalanceEntity, BalanceTransactionEntity
    │   │   ├── enum.py         -- TransactionType
    │   │   ├── dto.py          -- BalanceResponseDTO, TransactionListResponseDTO
    │   │   ├── consumer.py     -- handle_quiz_reward_message + start_consumer
    │   │   ├── router.py       -- Balance and transaction routes
    │   │   ├── models/
    │   │   │   ├── balance.py
    │   │   │   └── balance_transaction.py
    │   │   ├── repositories/
    │   │   │   ├── balance.py
    │   │   │   └── balance_transaction.py
    │   │   ├── service/
    │   │   │   └── balance.py  -- BalanceService (credit_from_quiz_event, get_balance, get_transactions)
    │   │   └── dependencies/
    │   │       └── service.py
    └── tests/
        ├── conftest.py
        ├── unit/
        │   ├── test_balance_repositories.py
        │   └── test_balance_service.py
        └── e2e/
            ├── test_routes.py
            └── test_consumer.py
```

---

## 4. Technology Stack

| Component | Technology | Notes |
|---|---|---|
| Web framework | FastAPI 0.115+ | Async only, lifespan-based startup |
| Language | Python 3.12 | Uses slots dataclasses, union type syntax |
| ORM | SQLAlchemy 2.x async | Mapped[] type annotations, async_sessionmaker |
| Database (quiz) | PostgreSQL 16 | JSONB for localized text and answer payloads |
| Database (balance) | PostgreSQL 16 | BigInteger amounts, UUID primary keys |
| Cache | Redis 7 | Quiz catalogue caching, allkeys-lru eviction |
| Message broker | RabbitMQ 3.13 | Topic exchange, durable queues, dead-letter queue |
| Migrations | Alembic | Async engine, autogenerate from ORM models |
| Serialization | Pydantic v2 | Settings via pydantic-settings, strict typed DTOs |
| Logging | structlog | JSON output, context vars for request-scoped fields |
| Containerization | Docker / Docker Compose | Multi-stage builds, non-root user |
| Package management | uv | Fast pip replacement used in Dockerfile layers |
| Testing | pytest + pytest-asyncio | asyncio_mode=auto |

---

## 5. Shared Library

The shared/ directory is an installable Python package named finelo-shared. Both service Dockerfiles install it via uv pip install /shared during the builder stage.

It provides three concerns:

### Exceptions

All domain exceptions inherit from FineloBaseException, which carries a message string and a code string. The FastAPI exception handlers in each service catch specific subtypes and map them to appropriate HTTP status codes.

```
FineloBaseException
  NotFoundException              --> HTTP 404
  ConflictException              --> HTTP 409
    AttemptAlreadyCompletedException
    AttemptExpiredException
    IdempotencyMismatchError
  ValidationException            --> HTTP 422
  ForbiddenException             --> HTTP 403 (needs explicit handler, see known issues)
  InternalServerException        --> HTTP 500
  InsufficientBalanceException
```

### Logging

configure_logging() sets up a structlog pipeline that emits JSON-formatted log lines to stdout. It binds the service name to every log entry using context vars, so all output from a running container is automatically tagged with the service name. Calling code uses get_logger(__name__) to obtain a bound logger.

### Cross-service schemas

EventEnvelope is the base for all published events. It carries a globally unique event_id UUID, event_type string, schema_version, and occurred_at timestamp. QuizRewardEvent specializes it:

```python
class QuizRewardPayload(BaseModel):
    user_id: uuid.UUID
    quiz_id: uuid.UUID
    attempt_id: uuid.UUID
    newly_rewarded_question_ids: list[uuid.UUID]
    coins_to_award: int

class QuizRewardEvent(EventEnvelope):
    event_type: str = 'quiz.questions.rewarded'
    payload: QuizRewardPayload
```

Both services depend on this schema. Any change to the payload format must be backward compatible or require a schema version bump.

### Messaging abstractions

MessagePublisher and MessageConsumer are runtime-checkable Protocols that define the three-method interface (connect, publish/consume, close). This allows service code to depend on the abstraction rather than a concrete broker client.

RabbitMQPublisher and RabbitMQConsumer implement these protocols using aio-pika. KafkaPublisher and KafkaConsumer using aiokafka are also included for environments where Kafka is preferred — the messaging layer is fully pluggable.

---

## 6. Quiz Service

### 6.1 Domain Model

The quiz service works with two aggregate roots:

Quiz is a container with a localized title, a localized optional description, an active flag, and an ordered list of Questions.

Question belongs to one Quiz and carries a QuestionType, an order_index for display ordering, a localized text JSONB map, and a payload JSONB map. The payload structure varies by question type and is described fully in section 6.3.

For the attempt sub-domain:

QuizAttempt tracks a single user's attempt at a quiz. It progresses through the states in_progress, completed, and abandoned. It records a score and total_questions count when completed.

UserQuestionAnswer records one answer per question within an attempt. The is_correct field is null while a draft answer is auto-saved and is populated only when the attempt is submitted and graded.

UserRewardedQuestion is a composite-primary-key table (user_id, question_id) that permanently records which questions a user has been financially rewarded for. It is the source of truth for reward idempotency.

OutboxEvent stores events that need to be published to the message broker, written in the same transaction as the business data they describe.

### 6.2 Database Schema

```
quizzes
  id           UUID PK
  title        JSONB NOT NULL          -- {"en": "...", "de": "...", ...}
  description  JSONB
  is_active    BOOLEAN DEFAULT TRUE
  created_at   TIMESTAMPTZ
  updated_at   TIMESTAMPTZ

questions
  id           UUID PK
  quiz_id      UUID FK quizzes.id CASCADE DELETE
  type         VARCHAR(30)             -- single_choice|fill_gap|multiple_choice|matching
  order_index  INTEGER DEFAULT 0
  text         JSONB NOT NULL          -- {"en": "...", "de": "..."}
  payload      JSONB NOT NULL          -- type-specific structure (see section 6.3)
  created_at   TIMESTAMPTZ
  updated_at   TIMESTAMPTZ
  INDEX idx_questions_quiz_id ON (quiz_id)
  INDEX idx_questions_quiz_order ON (quiz_id, order_index)

quiz_attempts
  id               UUID PK
  quiz_id          UUID FK quizzes.id CASCADE DELETE
  user_id          UUID NOT NULL
  status           VARCHAR(20) DEFAULT 'in_progress'
  score            INTEGER
  total_questions  INTEGER
  started_at       TIMESTAMPTZ
  updated_at       TIMESTAMPTZ
  completed_at     TIMESTAMPTZ
  CHECK (score >= 0)
  CHECK (total_questions > 0)
  INDEX idx_quiz_attempts_quiz_id ON (quiz_id)
  INDEX idx_quiz_attempts_user_quiz ON (user_id, quiz_id)

user_question_answers
  id              UUID PK
  attempt_id      UUID FK quiz_attempts.id CASCADE DELETE
  question_id     UUID FK questions.id CASCADE DELETE
  answer_payload  JSONB NOT NULL          -- mirrors the submitted StrictAnswerPayload
  is_correct      BOOLEAN                 -- NULL until submission
  answered_at     TIMESTAMPTZ
  UNIQUE INDEX idx_uqa_attempt_question_unique ON (attempt_id, question_id)
  INDEX idx_uqa_attempt_id ON (attempt_id)
  INDEX idx_uqa_question_id ON (question_id)

user_rewarded_questions
  user_id      UUID PK
  question_id  UUID PK FK questions.id CASCADE DELETE
  quiz_id      UUID FK quizzes.id CASCADE DELETE
  rewarded_at  TIMESTAMPTZ

outbox_events
  id           UUID PK
  event_type   VARCHAR(100) NOT NULL
  routing_key  VARCHAR(200) NOT NULL
  payload      JSONB NOT NULL
  created_at   TIMESTAMPTZ
  published_at TIMESTAMPTZ              -- NULL until successfully published
  attempts     INTEGER DEFAULT 0
  PARTIAL INDEX idx_outbox_pending_events ON (published_at) WHERE published_at IS NULL
```

### 6.3 Question Types

All question types share the same top-level structure in the database. The text field is always a locale map. The payload field contains both the display-time data (options, pairs) and the grading data (correct answers). When a question is returned to the client via the GET quiz endpoint, the localization service strips the grading data out of the payload before serialization.

#### single_choice

A question that displays several options and expects exactly one to be selected.

Payload stored in database:

```json
{
  "correct_id": "uuid-of-the-correct-option",
  "options": [
    {
      "id": "uuid-of-option-a",
      "text": {
        "en": "True",
        "de": "Wahr"
      }
    },
    {
      "id": "uuid-of-option-b",
      "text": {
        "en": "False",
        "de": "Falsch"
      }
    }
  ]
}
```

Payload returned to client (grading data stripped, text extracted for locale):

```json
{
  "options": [
    {"id": "uuid-of-option-a", "text": "True"},
    {"id": "uuid-of-option-b", "text": "False"}
  ]
}
```

Answer submission payload:

```json
{
  "question_type": "single_choice",
  "selected_id": "uuid-of-option-a"
}
```

Grading logic: string comparison of selected_id against correct_id.

#### multiple_choice

A question that expects one or more options to be selected. All must be selected and no extras.

Payload stored in database:

```json
{
  "correct_ids": [
    "uuid-option-a",
    "uuid-option-c"
  ],
  "options": [
    {
      "id": "uuid-option-a",
      "text": {"en": "Stocks", "de": "Aktien"}
    },
    {
      "id": "uuid-option-b",
      "text": {"en": "Bonds", "de": "Anleihen"}
    },
    {
      "id": "uuid-option-c",
      "text": {"en": "ETFs", "de": "ETFs"}
    }
  ]
}
```

Payload returned to client:

```json
{
  "options": [
    {"id": "uuid-option-a", "text": "Stocks"},
    {"id": "uuid-option-b", "text": "Bonds"},
    {"id": "uuid-option-c", "text": "ETFs"}
  ]
}
```

Answer submission payload:

```json
{
  "question_type": "multiple_choice",
  "selected_ids": ["uuid-option-a", "uuid-option-c"]
}
```

Grading logic: set equality between selected_ids and correct_ids.

#### fill_gap

A question with a blank that the user fills with free text. Accepts multiple valid answers to handle case and whitespace variations.

Payload stored in database:

```json
{
  "correct_answers": [
    "Rossum",
    "rossum",
    "ROSSUM"
  ]
}
```

Payload returned to client: empty object (nothing to display beyond the question text itself):

```json
{}
```

Answer submission payload:

```json
{
  "question_type": "fill_gap",
  "answer": "Rossum"
}
```

Grading logic: the submitted answer is stripped of leading and trailing whitespace, lowercased, and compared against each correct_answer after applying the same normalization. This handles the case where the stored answers include variations but the comparison itself is case-insensitive.

#### matching

A question that presents pairs where the left and right sides must be correctly associated. The client must return a mapping of pair_id to matched_pair_id.

Payload stored in database:

```json
{
  "pairs": [
    {
      "pair_id": "uuid-left-a",
      "left": {"en": "Bull market", "de": "Bullenmarkt"},
      "right": {"en": "Prices rising", "de": "Steigende Preise"},
      "right_id": "uuid-right-a"
    },
    {
      "pair_id": "uuid-left-b",
      "left": {"en": "Bear market", "de": "Barenmarkt"},
      "right": {"en": "Prices falling", "de": "Fallende Preise"},
      "right_id": "uuid-right-b"
    }
  ]
}
```

Payload returned to client (correct associations hidden):

```json
{
  "pairs": [
    {
      "pair_id": "uuid-left-a",
      "left": "Bull market",
      "right": "Prices rising"
    },
    {
      "pair_id": "uuid-left-b",
      "left": "Bear market",
      "right": "Prices falling"
    }
  ]
}
```

Answer submission payload:

```json
{
  "question_type": "matching",
  "pairs": [
    {
      "pair_id": "uuid-left-a",
      "matched_pair_id": "uuid-right-a"
    },
    {
      "pair_id": "uuid-left-b",
      "matched_pair_id": "uuid-right-b"
    }
  ]
}
```

Grading logic: builds a map from pair_id to right_id from the stored payload and verifies that every submitted pair matches. Counts and set membership must both match.

### 6.4 Localization Design

Quiz titles, descriptions, and question texts are stored as JSONB dictionaries whose keys are ISO 639-1 language codes:

```json
{
  "en": "What is an ETF?",
  "de": "Was ist ein ETF?",
  "es": "Que es un ETF?",
  "fr": "Qu'est-ce qu'un ETF ?",
  "pt": "O que e um ETF?",
  "tr": "ETF nedir?",
  "it": "Cos'e un ETF?",
  "id": "Apa itu ETF?",
  "fil": "Ano ang ETF?"
}
```

The locale is extracted from the Accept-Language HTTP header. The ILocale dependency parses the header, takes the primary language tag, strips region codes (en-US becomes en), and defaults to en. The QuizLocalizationService.extract_text() method performs a three-step fallback: it looks for the requested locale, then falls back to en, then falls back to the first available key. This guarantees that a response is always returned even for a language that was not yet added to the content.

This design means adding support for a new language requires no schema change, only content updates.

### 6.5 Caching Layer

The quiz service uses Redis to cache quiz catalogue and quiz detail responses. The CachingQuizRepository wraps the real QuizRepository with a cache-aside pattern:

1. On read: compute a cache key, check Redis, return the deserialized entity if found.
2. On miss: query PostgreSQL, serialize the entity to JSON, write it to Redis with a TTL, return the entity.
3. On write (create, update, status change): invalidate the affected cache keys.

The TTL defaults to 60 seconds and is controlled by the QUIZ_CACHE_TTL environment variable. The cache key format is quiz:{quiz_id} for individual quizzes and quiz:catalogue:{limit}:{offset} for paginated listings.

This layer is transparent to the service code: AttemptService and QuizService depend on the IUnitOfWork interface which exposes a quizzes repository attribute. At runtime that attribute holds a CachingQuizRepository instance.

### 6.6 Transactional Outbox Pattern

The challenge: when a quiz attempt is submitted, two things must happen atomically: the attempt's state must be updated in the database, and a reward event must be delivered to the balance service. If the database write succeeds but the broker publish fails, the balance is never credited. If the broker publish succeeds but the database write fails, the balance is credited for an attempt that does not exist.

The transactional outbox pattern solves this by making the event write part of the same database transaction as the business state change.

Flow:

1. The submit_attempt service method opens a UoW and performs all of its database writes:
   - Bulk inserts graded UserQuestionAnswer rows.
   - Updates the QuizAttempt to COMPLETED.
   - Calls RewardService.process_rewards(), which inserts UserRewardedQuestion rows for newly rewarded questions and writes an OutboxEvent row.
   - Commits the transaction.

2. A background worker (the outbox worker) runs on a configurable OUTBOX_POLL_INTERVAL (default: 2 seconds) within the quiz service process. On each tick it:
   - Opens a database session.
   - Fetches a batch of unpublished outbox events (WHERE published_at IS NULL) using SELECT ... FOR UPDATE SKIP LOCKED to safely handle concurrent workers.
   - For each event, publishes it to RabbitMQ using the stored routing_key.
   - On success, stamps published_at with the current timestamp.
   - On failure, increments the attempts counter and continues to the next event.

3. The balance service receives the event, processes it, and credits the balance.

The partial index on outbox_events(published_at) WHERE published_at IS NULL makes the pending-event polling query efficient as the table grows, since it only indexes rows that have not yet been published.

At-least-once delivery is guaranteed: an event may be published more than once if the outbox worker publishes successfully but crashes before writing published_at. The balance service handles this through idempotency keys described in section 7.4.

### 6.7 Reward Idempotency

To ensure a user receives coins only once per correctly answered question (across all attempts at the same quiz), a user_rewarded_questions table acts as a permanent ledger.

When RewardService.process_rewards() is called:

1. It queries user_rewarded_questions for all question IDs that the user has already been rewarded for.
2. It subtracts the already-rewarded set from the current attempt's correctly answered set.
3. Only the difference (newly rewarded IDs) receives a reward.
4. The newly rewarded rows are inserted into user_rewarded_questions within the same transaction.
5. The reward event is constructed with newly_rewarded_question_ids and coins_to_award reflecting only the new rewards.

If the user retakes the quiz and answers the same questions correctly, the process_rewards call returns an empty list, no event is staged, and coins_awarded is 0 in the response.

### 6.8 Attempt Lifecycle

```
quiz active?
    |
    | POST /attempts/{quiz_id}/start
    v
[IN_PROGRESS]  <---- PUT /attempts/{attempt_id}/answers  (auto-save draft, idempotent upsert)
    |
    +-------> POST /attempts/{attempt_id}/abandon  --> [ABANDONED]
    |
    | POST /attempts/{attempt_id}/submit
    v
[COMPLETED]
    (score, coins_awarded, question_results returned)
```

The validate_attempt_access static method enforces three invariants before any mutation:

- The attempt must exist (NotFoundException if not found).
- The attempt must belong to the requesting user (ForbiddenException if user_id does not match).
- The attempt must still be IN_PROGRESS (AttemptAlreadyCompletedException otherwise).

Concurrent submission protection is implemented via SELECT ... FOR UPDATE on the attempt row. PostgreSQL holds a row-level exclusive lock until the surrounding transaction is committed or rolled back, preventing any concurrent session from reading a stale status.

An attempt abandonment background job runs in the service lifespan to handle stalled sessions. It periodically queries the repository's `bulk_mark_abandoned` method to transition stale, inactive IN_PROGRESS attempts to ABANDONED automatically, ensuring that abandoned sessions do not persist indefinitely.

### 6.9 API Reference

All quiz service endpoints are served on port 8002 (host) mapped to 8000 in the container.

Base URL: http://localhost:8002

Interactive documentation: http://localhost:8002/docs (Swagger UI) or http://localhost:8002/redoc

#### GET /health/live

Returns 200 immediately. Used by Docker health checks and load balancers as a liveness probe.

Response:

```json
{"status": "ok"}
```

#### GET /health/ready

Checks database connectivity and Redis connectivity. Returns 200 if all checks pass, 503 otherwise.

Response (healthy):

```json
{
  "status": "ready",
  "checks": {
    "database": "ok",
    "redis": "ok"
  }
}
```

Response (degraded):

```json
{
  "status": "degraded",
  "checks": {
    "database": "ok",
    "redis": "error: Connection refused"
  }
}
```

#### GET /api/v1/quizzes

Returns a paginated, localized list of active quizzes.

Query parameters:

| Parameter | Type | Default | Constraints | Description |
|---|---|---|---|---|
| limit | integer | 50 | 1 to 100 | Maximum number of results |
| offset | integer | 0 | >= 0 | Number of records to skip |

Headers:

| Header | Required | Description |
|---|---|---|
| Accept-Language | optional | ISO language code. Defaults to en |

Response 200:

```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "Introduction to ETFs",
      "description": "Learn the basics of exchange-traded funds.",
      "question_count": 5
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 50
}
```

#### GET /api/v1/quizzes/{quiz_id}

Returns the full localized structure of a single active quiz, including all questions with their display-safe payloads. Correct answers are never included in this response.

Path parameters:

| Parameter | Type | Description |
|---|---|---|
| quiz_id | UUID | The quiz identifier |

Headers:

| Header | Required | Description |
|---|---|---|
| Accept-Language | optional | ISO language code. Defaults to en |

Response 200:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Introduction to ETFs",
  "description": "Learn the basics of exchange-traded funds.",
  "questions": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "type": "single_choice",
      "order_index": 0,
      "text": "What does ETF stand for?",
      "payload": {
        "options": [
          {"id": "opt-uuid-1", "text": "Exchange-Traded Fund"},
          {"id": "opt-uuid-2", "text": "Equity Transfer Fund"},
          {"id": "opt-uuid-3", "text": "Early Trading Form"}
        ]
      }
    },
    {
      "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "type": "fill_gap",
      "order_index": 1,
      "text": "ETFs trade on exchanges like ___ throughout the day.",
      "payload": {}
    }
  ]
}
```

Response 404:

```json
{
  "error": {
    "code": "NotFoundException",
    "message": "Quiz 550e8400-e29b-41d4-a716-446655440000 is not found or currently inactive."
  }
}
```

#### POST /api/v1/quizzes

Creates a new quiz. New quizzes are created in inactive state and must be explicitly activated before they are visible to users.

Request body:

```json
{
  "title": {
    "en": "Introduction to ETFs",
    "de": "Einführung in ETFs",
    "es": "Introducción a los ETF"
  },
  "description": {
    "en": "Learn the basics of exchange-traded funds.",
    "de": "Lernen Sie die Grundlagen von Exchange-Traded Funds."
  },
  "questions": [
    {
      "type": "single_choice",
      "text": {
        "en": "What does ETF stand for?",
        "de": "Wofür steht ETF?"
      },
      "payload": {
        "correct_id": "opt-uuid-1",
        "options": [
          {
            "id": "opt-uuid-1",
            "text": {
              "en": "Exchange-Traded Fund",
              "de": "Börsengehandelter Fonds"
            }
          },
          {
            "id": "opt-uuid-2",
            "text": {
              "en": "Equity Transfer Fund",
              "de": "Eigenkapitalübertragungsfonds"
            }
          }
        ]
      }
    }
  ]
}
```

Response 201:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000"
}
```

#### PATCH /api/v1/quizzes/{quiz_id}/status

Activates or deactivates a quiz. Only active quizzes appear in the catalogue or can be started by users.

Request body:

```json
{"is_active": true}
```

Response 204: No content.

Response 404:

```json
{
  "error": {
    "code": "NotFoundException",
    "message": "Quiz 550e8400-e29b-41d4-a716-446655440000 does not exist."
  }
}
```

#### POST /api/v1/quizzes/{quiz_id}/questions

Appends a new question to an existing quiz. The new question is appended at the end (order_index = current count of questions).

Request body follows the same structure as a question in CreateQuizDTO (see POST /api/v1/quizzes above).

Response 201:

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

#### PUT /api/v1/quizzes/{quiz_id}/questions/{question_id}

Replaces the text, payload, and type of an existing question.

Request body: same structure as for question creation.

Response 204: No content.

Response 404 if the question does not exist.

#### DELETE /api/v1/quizzes/{quiz_id}/questions/{question_id}

Hard-deletes a question. CASCADE DELETE in the database removes associated user_question_answers.

Response 204: No content.

Response 404 if the question does not exist.

#### POST /api/v1/attempts/{quiz_id}/start

Creates a new in-progress attempt for the specified quiz. Requires X-User-ID header.

Headers:

| Header | Required | Description |
|---|---|---|
| X-User-ID | required | The authenticated user's UUID |

Response 201:

```json
{
  "attempt_id": "cc7a20db-1234-5678-abcd-000000000001",
  "quiz_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "11111111-1111-1111-1111-111111111111"
}
```

Response 404 if the quiz does not exist or is inactive.

#### PUT /api/v1/attempts/{attempt_id}/answers

Saves or updates a single draft answer for an active attempt. This is an upsert: submitting the same question_id twice overwrites the previous draft. Does not affect grading and does not modify the attempt status.

Headers: X-User-ID required.

Request body:

```json
{
  "answer": {
    "question_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "answer_payload": {
      "question_type": "single_choice",
      "selected_id": "opt-uuid-1"
    }
  }
}
```

Response 204: No content.

Response 404 if the attempt is not found.

Response 409 if the attempt is no longer in progress.

Response 403 if the attempt belongs to a different user.

#### POST /api/v1/attempts/{attempt_id}/submit

Finalizes the attempt, grades all submitted answers, calculates rewards, stages the outbox event, and returns the result.

Headers: X-User-ID required.

Request body:

```json
{
  "answers": [
    {
      "question_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "answer_payload": {
        "question_type": "single_choice",
        "selected_id": "opt-uuid-1"
      }
    },
    {
      "question_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "answer_payload": {
        "question_type": "fill_gap",
        "answer": "ETF"
      }
    }
  ]
}
```

Response 200:

```json
{
  "attempt_id": "cc7a20db-1234-5678-abcd-000000000001",
  "score": 2,
  "total_questions": 2,
  "coins_awarded": 200,
  "question_results": [
    {
      "question_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "is_correct": true,
      "was_already_rewarded": false
    },
    {
      "question_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "is_correct": true,
      "was_already_rewarded": false
    }
  ]
}
```

The was_already_rewarded flag in each question_result is true when a question was answered correctly in a previous attempt. In that case the question contributes to score but not to coins_awarded.

Response 409 if the attempt is already completed.

Response 403 if the attempt belongs to a different user.

Response 422 if an answer references a question_id that does not belong to this quiz.

#### POST /api/v1/attempts/{attempt_id}/abandon

Explicitly marks an in-progress attempt as abandoned. No further answers can be submitted to it.

Headers: X-User-ID required.

Response 204: No content.

Response 404 if not found, 403 if not owned by the requesting user, 409 if already completed.

---

## 7. Balance Service

### 7.1 Domain Model

The balance service maintains two aggregate roots:

Balance is a per-user running total. It has exactly one row per user (enforced by a UNIQUE constraint on user_id). The amount is stored as BigInteger to avoid floating-point precision issues.

BalanceTransaction is an immutable ledger entry recording each credit or debit operation. It carries the amount, a human-readable description, and an idempotency_key UUID that prevents duplicate processing.

### 7.2 Database Schema

```
balances
  id          UUID PK
  user_id     UUID UNIQUE NOT NULL
  amount      BIGINT DEFAULT 0
  updated_at  TIMESTAMPTZ
  CHECK (amount >= 0)

balance_transactions
  id               UUID PK
  user_id          UUID NOT NULL
  type             VARCHAR(10) NOT NULL     -- 'credit' or 'debit'
  amount           BIGINT NOT NULL
  description      VARCHAR(255)
  idempotency_key  UUID UNIQUE NOT NULL     -- maps to event_id from the quiz service
  created_at       TIMESTAMPTZ
  CHECK (amount > 0)
  INDEX idx_txn_user_id ON (user_id)
```

The CHECK (amount >= 0) constraint on balances prevents the service from ever producing a negative balance at the database level. The UNIQUE constraint on balance_transactions.idempotency_key is the database-level enforcement of the idempotency guarantee.

### 7.3 Consumer and Supervisor

The balance service does not expose a webhook. Instead it consumes from RabbitMQ. The consumer is started inside the lifespan context manager via a supervisor task.

The supervisor (_supervise_consumer) runs in an asyncio.Task and continuously monitors the consumer. If the consumer process raises any exception other than CancelledError, the supervisor catches it, logs the error, waits for an exponentially increasing delay (2 seconds for the first retry, 4, 8, ... capped at 60 seconds), and then reconnects. This exponential backoff prevents overwhelming RabbitMQ with reconnection attempts after a broker restart.

The is_consumer_connected() function exposes consumer health to the /health/ready endpoint so the container orchestrator can detect messaging failures.

When a message is received:

1. The handler deserializes the body as a QuizRewardEvent using Pydantic's model_validate_json.
2. If deserialization fails (malformed JSON or schema mismatch), the exception propagates and aio-pika negatively acknowledges the message, routing it to the DLQ.
3. On success, it creates a SqlAlchemyUnitOfWork, opens a session, and calls BalanceService.credit_from_quiz_event().
4. If the service call raises any exception (including database errors), the exception propagates and aio-pika negatively acknowledges the message.
5. If everything succeeds, aio-pika positively acknowledges the message.

### 7.4 Idempotent Credits

The credit_from_quiz_event method uses two mechanisms to guarantee exactly-once crediting:

The first mechanism is the unique constraint on balance_transactions.idempotency_key. The event's event_id UUID is used as the idempotency_key. The insert uses INSERT ... ON CONFLICT DO NOTHING ... RETURNING. If the row already exists (a duplicate delivery), the insert silently succeeds with no rows returned, and the method reads the existing balance rather than modifying it.

The second mechanism is the _resolve_duplicate_event method, which is called when insert_idempotent returns None (the conflicting case). It reads the existing transaction by idempotency_key and verifies that its amount matches the expected amount. If the amounts differ, it raises IdempotencyMismatchError, which signals a logic error (two different events sharing the same ID with different amounts, which should never happen in a correctly operating system). If the amounts match, it reads and returns the current balance.

The balance upsert uses INSERT ... ON CONFLICT (user_id) DO UPDATE SET amount = amount + excluded.amount. This is an atomic increment, meaning it creates the balance row for a new user or adds to it for an existing user in a single statement without a read-modify-write race condition.

### 7.5 API Reference

All balance service endpoints are served on port 8001.

Base URL: http://localhost:8001

Interactive documentation: http://localhost:8001/docs

#### GET /health/live

Returns 200. Liveness probe.

Response:

```json
{"status": "ok"}
```

#### GET /health/ready

Checks database connectivity and consumer connection state.

Response 200 (healthy):

```json
{
  "status": "ready",
  "checks": {
    "database": "ok",
    "messaging": "ok"
  }
}
```

Response 503 (degraded):

```json
{
  "status": "degraded",
  "checks": {
    "database": "ok",
    "messaging": "disconnected"
  }
}
```

#### GET /api/v1/balances/{user_id}

Returns the current balance for a specific user. If the user has never received coins, returns 0.

Path parameters:

| Parameter | Type | Description |
|---|---|---|
| user_id | UUID | The user's identifier |

Response 200:

```json
{
  "user_id": "11111111-1111-1111-1111-111111111111",
  "amount": 1500,
  "updated_at": "2026-03-26T12:34:56.789Z"
}
```

#### GET /api/v1/balances/{user_id}/transactions

Returns a paginated, reverse-chronological list of credit and debit transactions for a user.

Query parameters:

| Parameter | Type | Default | Constraints | Description |
|---|---|---|---|---|
| page | integer | 1 | >= 1 | The 1-based page number |
| page_size | integer | 50 | 1 to 100 | Transactions per page |

Response 200:

```json
{
  "items": [
    {
      "id": "txn-uuid-1",
      "user_id": "11111111-1111-1111-1111-111111111111",
      "type": "credit",
      "amount": 300,
      "description": "Quiz reward: attempt cc7a20db-1234-5678-abcd-000000000001",
      "created_at": "2026-03-26T12:34:56.789Z"
    }
  ],
  "page": 1,
  "page_size": 50,
  "total": 1
}
```

---

## 8. Service Communication Flow

This section traces the complete data flow from a user submitting a quiz attempt to the balance being updated.

```
Step 1: Client submits attempt
  POST http://localhost:8002/api/v1/attempts/{attempt_id}/submit
  Header: X-User-ID: 11111111-1111-1111-1111-111111111111
  Body: { "answers": [...] }

Step 2: quiz_service processes submission (single transaction)
  a. SELECT quiz_attempts WHERE id = {attempt_id} FOR UPDATE
  b. Validate user owns the attempt and it is in_progress
  c. SELECT questions WHERE id IN (submitted_question_ids)
  d. GradingService grades each answer against question payloads
  e. RewardService queries user_rewarded_questions for already-rewarded IDs
  f. INSERT into user_rewarded_questions for newly rewarded questions
  g. INSERT into outbox_events (event_type='quiz.rewarded', routing_key='finance.reward',
     payload={user_id, quiz_id, attempt_id, newly_rewarded_question_ids, coins_to_award})
  h. UPDATE quiz_attempts SET status='completed', score=N, total_questions=M
  i. INSERT into user_question_answers (graded rows)
  j. COMMIT

Step 3: quiz_service returns 200 immediately to the client
  Response: { "score": N, "total_questions": M, "coins_awarded": C, "question_results": [...] }

Step 4: Outbox worker (background, next poll cycle, typically within 2 seconds)
  a. SELECT from outbox_events WHERE published_at IS NULL FOR UPDATE SKIP LOCKED LIMIT 50
  b. For each event:
     - Publish to RabbitMQ exchange 'finelo.events' with routing key 'finance.reward'
     - UPDATE outbox_events SET published_at = NOW() WHERE id = {event_id}
  c. COMMIT

Step 5: RabbitMQ routes the message
  Exchange: finelo.events (topic type)
  Routing key: finance.reward
  Bound queue: balance.quiz_reward

Step 6: balance_service consumer receives the message
  a. Deserialize body as QuizRewardEvent
  b. Open SqlAlchemyUnitOfWork
  c. BalanceService.credit_from_quiz_event(event):
     i.  INSERT INTO balance_transactions
         (user_id, type='credit', amount=coins_to_award, idempotency_key=event.event_id)
         ON CONFLICT DO NOTHING RETURNING *
     ii. If row was inserted: upsert balance
         INSERT INTO balances (user_id, amount=coins_to_award)
         ON CONFLICT (user_id) DO UPDATE SET amount = amount + excluded.amount
     iii. If no row (duplicate): read existing balance, verify amount, return current balance
  d. COMMIT
  e. ACK message to RabbitMQ

Step 7: Balance is updated
  User now has updated amount in balance_service database
  Readable via GET http://localhost:8001/api/v1/balances/11111111-1111-1111-1111-111111111111
```

---

## 9. Infrastructure

The docker-compose.yml file defines the complete system with the following services:

quiz_db (PostgreSQL 16) runs on port 5432, using a named volume quiz_db_data for persistence. A health check using pg_isready ensures dependent services wait until the database is actually accepting connections.

balance_db (PostgreSQL 16) runs on port 5433, using a separate named volume balance_db_data. The two databases have no shared state.

redis (Redis 7) runs on port 6379 with a 256 MB memory cap and allkeys-lru eviction policy, so old cache entries are evicted automatically when memory is full.

rabbitmq (RabbitMQ 3.13 with management plugin) runs on ports 5672 (AMQP) and 15672 (management UI). The management UI is accessible at http://localhost:15672 with credentials guest/guest. It allows inspection of exchanges, queues, and message rates.

quiz_migrate runs the Alembic upgrade head command against quiz_db and exits. The condition service_completed_successfully on quiz_service's depends_on means the application container only starts after migrations complete successfully.

balance_migrate performs the same role for balance_db.

quiz_service runs on host port 8002, depends on quiz_db, redis, rabbitmq, and quiz_migrate.

balance_service runs on host port 8001, depends on balance_db, rabbitmq, and balance_migrate.

Both service containers use multi-stage Dockerfiles:

Stage 1 (builder): Installs uv, installs the shared library, installs service dependencies from pyproject.toml.

Stage 2 (runtime): Creates a non-root finelo user, copies the installed packages from builder, copies the application source, sets environment variables, exposes the port, and defines the CMD.

This separation keeps the runtime image smaller and prevents build tools from being present in production.

---

## 10. Running the Project

### Prerequisites

- Docker Desktop or Docker Engine with Compose v2
- No local Python installation required (everything runs in containers)

### Start all services

```bash
make up
```

This is equivalent to:

```bash
docker compose up --build -d
```

The first run will build images and take several minutes. Subsequent runs are fast because Docker caches layers.

### Wait for readiness

After the containers start, migration containers run and exit, then application containers start. You can follow logs with:

```bash
make logs
```

Or to follow only a specific service:

```bash
docker compose logs -f quiz_service
docker compose logs -f balance_service
```

The services are ready when the health check endpoints return:

```bash
curl http://localhost:8002/health/ready
# {"status":"ready","checks":{"database":"ok","redis":"ok"}}

curl http://localhost:8001/health/ready
# {"status":"ready","checks":{"database":"ok","messaging":"ok"}}
```

Note: messaging will show disconnected briefly while the consumer connects to RabbitMQ on startup. It resolves within a few seconds.

### Stop services

```bash
make down
```

### Stop and remove all volumes (full reset)

```bash
make clean
```

### Access RabbitMQ management UI

Navigate to http://localhost:15672 in a browser.

Username: guest
Password: guest

From here you can inspect the finelo.events exchange, the balance.quiz_reward queue, and the balance.quiz_reward.dlq dead-letter queue.

### Running locally without Docker (for development)

If you want to run a service directly with uvicorn while keeping infrastructure in Docker:

Start only infrastructure:

```bash
docker compose up quiz_db balance_db redis rabbitmq -d
```

For the quiz service:

```bash
cd quiz_service
pip install uv
uv pip install --system -e .
# Install the shared library first
uv pip install --system -e ../shared
# Run migrations
pip install alembic asyncpg
alembic upgrade head
# Start the service
uvicorn src.app:app --host 0.0.0.0 --port 8002 --reload
```

For the balance service:

```bash
cd balance_service
uv pip install --system -e .
uv pip install --system -e ../shared
alembic upgrade head
uvicorn src.app:app --host 0.0.0.0 --port 8001 --reload
```

---

## 11. Environment Variables Reference

### Quiz Service (.env or environment)

| Variable | Default | Description |
|---|---|---|
| APP_TITLE | Finelo Quiz Service | OpenAPI title |
| APP_DESCRIPTION | - | OpenAPI description |
| APP_VERSION | 1.0.0 | Displayed in OpenAPI spec |
| APP_HOST | 0.0.0.0 | Uvicorn bind host |
| APP_PORT | 8000 | Uvicorn bind port |
| APP_DEBUG | False | Enable debug mode |
| APP_HOOKS_ENABLED | True | Enable lifespan hooks (outbox worker, etc.) |
| APP_ROOT_PATH | (empty) | ASGI root path for reverse proxy prefix stripping |
| APP_TIMEZONE_SHIFT | 3 | Timezone offset for display (UTC+N) |
| DB_URL_SCHEME | postgresql+asyncpg | SQLAlchemy async driver prefix |
| DB_HOST | localhost | PostgreSQL host |
| DB_PORT | 5432 | PostgreSQL port |
| DB_NAME | test_db | Database name |
| DB_USER | test_user | Database user |
| DB_PASSWORD | test_password | Database password |
| DB_ECHO_LOG | False | Log all SQL statements |
| DB_RUN_AUTO_MIGRATE | False | Run Alembic on startup (not used currently) |
| DB_POOL_SIZE | 5 | SQLAlchemy connection pool size |
| DB_MAX_OVERFLOW | 10 | Maximum pool overflow connections |
| REDIS_URL | redis://localhost:6379/0 | Redis connection URL |
| QUIZ_CACHE_TTL | 60 | Quiz cache TTL in seconds |
| RABBITMQ_URL | amqp://guest:guest@localhost:5672/ | RabbitMQ AMQP connection URL |
| RABBITMQ_EXCHANGE | finelo.events | RabbitMQ topic exchange name |
| RABBITMQ_ROUTING_KEY | quiz.questions.rewarded | Routing key for quiz reward events |
| OUTBOX_POLL_INTERVAL | 2.0 | Outbox worker polling interval in seconds |
| OUTBOX_BATCH_SIZE | 50 | Outbox events per polling batch |
| ATTEMPT_ABANDON_POLL_INTERVAL | 60.0 | Polling interval (seconds) for the attempt abandonment background job |
| ATTEMPT_ABANDON_TIMEOUT_MINUTES | 60 | Inactivity threshold before an attempt is considered abandoned |
| QUIZ_COINS_PER_CORRECT_ANSWER | 100 | Coins awarded per correctly answered question |
| QUIZ_REWARD_ROUTING_KEY | quiz.questions.rewarded | Routing key embedded in outbox events |
| LOGGING_ON | True | Enable logging |
| LOGGING_LEVEL | INFO | Log level |
| LOGGING_JSON | False | Use JSON log format |
| CORS_ALLOW_ORIGINS | * | Comma-delimited allowed origins |
| CORS_ALLOW_METHODS | GET,POST,PUT,DELETE,PATCH,OPTIONS | Comma-delimited allowed HTTP methods |
| CORS_ALLOW_HEADERS | * | Comma-delimited allowed headers |
| CORS_ALLOW_CREDENTIALS | true | Allow credentials |
| CORS_EXPOSE_HEADERS | * | Comma-delimited exposed headers |
| CORS_MAX_AGE | 600 | Preflight cache duration in seconds |

### Balance Service (.env or environment)

| Variable | Default | Description |
|---|---|---|
| APP_TITLE | Finelo Balance Service | OpenAPI title |
| APP_VERSION | 1.0.0 | Displayed in OpenAPI spec |
| APP_HOST | 0.0.0.0 | Uvicorn bind host |
| APP_PORT | 8001 | Uvicorn bind port |
| APP_DEBUG | True | Enable debug mode (should be False in production) |
| DB_URL_SCHEME | postgresql+asyncpg | SQLAlchemy async driver prefix |
| DB_HOST | (required) | PostgreSQL host |
| DB_PORT | (required) | PostgreSQL port |
| DB_NAME | (required) | Database name |
| DB_USER | (required) | Database user |
| DB_PASSWORD | (required) | Database password |
| DB_ECHO_LOG | False | Log all SQL statements |
| DB_POOL_SIZE | 5 | SQLAlchemy connection pool size |
| DB_MAX_OVERFLOW | 10 | Maximum pool overflow connections |
| RABBITMQ_URL | amqp://guest:guest@localhost:5672/ | RabbitMQ AMQP connection URL |
| RABBITMQ_EXCHANGE | finelo.events | RabbitMQ topic exchange name |
| RABBITMQ_QUEUE | balance.quiz_reward | RabbitMQ queue name to consume from |
| RABBITMQ_ROUTING_KEY | quiz.questions.rewarded | Binding key for the queue |
| LOGGING_ON | True | Enable logging |
| LOGGING_LEVEL | DEBUG | Log level |
| LOGGING_JSON | True | Use JSON log format |
| CORS_ALLOW_ORIGINS | * | Comma-delimited allowed origins |

---

## 12. Database Migrations

Both services use Alembic with an async SQLAlchemy engine. The migrations are run by dedicated one-shot containers (quiz_migrate and balance_migrate) that exit after completing. The application containers only start after the migration containers exit successfully.

To generate a new migration after modifying an ORM model:

```bash
# For quiz service
cd quiz_service
alembic revision --autogenerate -m "describe the change"

# For balance service
cd balance_service
alembic revision --autogenerate -m "describe the change"
```

Alembic's autogenerate compares the current ORM metadata against the database schema and produces an upgrade script. Always review the generated migration before committing it, as autogenerate can miss some changes (e.g., server-side default values or complex constraints).

To apply migrations manually:

```bash
alembic upgrade head
```

To roll back one migration:

```bash
alembic downgrade -1
```

The current migration for the balance service (revision 9b6cd6f575ab) creates the balance_transactions and balances tables with all constraints and indexes as described in section 7.2. The quiz service has its own migration history for quizzes, questions, quiz_attempts, user_question_answers, user_rewarded_questions, and outbox_events.

---

## 13. Running Tests

Tests are organized per service. Each service has its own pytest configuration in pytest.ini.

### Quiz Service Tests

From the project root (or use the Docker approach below):

```bash
cd quiz_service
pip install -e ".[test]"
pip install -e ../shared
pytest
```

Or via Docker:

```bash
docker compose run --rm quiz_service pytest
```

Run with verbose output:

```bash
pytest -v
```

Run a specific test file:

```bash
pytest tests/unit/test_grading_service.py -v
pytest tests/integration/test_routes.py -v
pytest tests/integration/test_race_condition.py -v
```

### Balance Service Tests

```bash
cd balance_service
pip install -e ".[test]"
pip install -e ../shared
pytest
```

Or via Docker:

```bash
docker compose run --rm balance_service pytest
```

### Test dependencies

The pyproject.toml in each service defines test dependencies in an optional [test] group. These include:

- pytest
- pytest-asyncio
- pytest-mock (if used)

The asyncio_mode = auto setting in pytest.ini means all test functions and methods decorated with @pytest.mark.asyncio or in an async def context are automatically collected without needing explicit markers.

---

## 14. Test Coverage Breakdown

### Quiz Service Tests

#### tests/unit/test_grading_service.py

Tests the GradingService in complete isolation. No database, no UoW, no mocks beyond question entities. Covers all four question types:

- Single choice: correct selection, wrong selection
- Multiple choice: exact match, missing selection, extra selection, empty submission
- Fill gap: exact match, case-insensitive match, whitespace-trimmed match, wrong answer
- Matching: all pairs correct, one pair wrong, extra pairs, missing pairs, empty submission

#### tests/unit/test_reward_service.py

Tests RewardService against a mocked UoW. Covers:

- All questions newly rewarded: full reward issued, correct outbox event staged
- All questions already rewarded: no reward, no outbox event
- Mixed: partial reward, outbox reflects only new questions
- Empty correct_question_ids list: short-circuits with empty return
- Coin calculation: coins = count(newly_rewarded) * COINS_PER_CORRECT_ANSWER

#### tests/unit/test_attempt_service.py

Tests AttemptService against a mocked UoW, mocked GradingService, and mocked RewardService. Covers:

- Start attempt: quiz not found raises NotFoundException, quiz inactive raises NotFoundException, valid start returns DTO
- Auto-save: valid upsert, attempt not found, wrong user raises ForbiddenException, completed attempt raises AttemptAlreadyCompletedException
- Abandon: transitions to ABANDONED, same ownership checks
- Submit: successful submission with score and coin calculation, already-completed attempt raises, unknown question IDs raise ValidationException, wrong user raises ForbiddenException
- was_already_rewarded flag: correctly set for questions that were rewarded in prior attempts

#### tests/integration/test_routes.py

End-to-end HTTP tests using FastAPI's TestClient. Services are replaced with AsyncMock instances via dependency_overrides. No real database is used. Covers:

- All attempt routes: 201 start, 204 auto-save, 200 submit, 204 abandon
- Error mapping: 404 for NotFoundException, 409 for conflict, 422 for validation, 400 for bad UUID header
- All quiz CRUD routes: 200 list, 404 get, 201 create, 204 status update, 201 append question, 204 delete question, 404 on delete not found
- Pagination enforcement: limit out of range returns 422
- Health routes: 200 liveness

#### tests/integration/test_race_condition.py

Specialized tests simulating concurrent submissions to the same attempt:

- Sequential double submit: first succeeds, second raises AttemptAlreadyCompletedException because the DB state transitions to COMPLETED between calls
- Concurrent submits via asyncio.gather: uses asyncio.Lock to simulate the mutual exclusion that SELECT FOR UPDATE provides in PostgreSQL; exactly one succeeds
- Caching: CachingQuizRepository cache miss queries database, cache hit returns cached value, invalidation after status change results in a miss on next read

### Balance Service Tests

#### tests/unit/test_balance_repositories.py

Tests BalanceRepository and BalanceTransactionRepository against mocked AsyncSession objects. Covers:

- get_by_user_id: returns entity when found, returns None when not found, entity fields mapped correctly
- upsert_amount: returns updated entity, execute called once, zero amount creates balance
- get_by_idempotency_key: found and not found cases, entity type verification
- insert_idempotent: returns entity on success, returns None on duplicate key (ON CONFLICT DO NOTHING)
- get_paginated_by_user: returns list of entities
- count_by_user: returns integer count

#### tests/unit/test_balance_service.py

Tests BalanceService against a mocked UoW and mocked repositories. Covers:

- credit_from_quiz_event: new user credited correctly, duplicate event detected and silently ignored, existing user balance incremented
- _resolve_duplicate_event: None returned (race condition, not yet visible), matching amount silently ignored, different amount raises IdempotencyMismatchError, no balance for user creates zero balance
- get_transactions: empty history, single page, page 2 offset, page metadata, field mapping, page size of 1, first page offset zero, database error propagates
- get_balance: found, not found creates zero balance

#### tests/e2e/test_routes.py

HTTP route tests for the balance service using TestClient with dependency overrides and mocked RabbitMQ consumer startup. Covers:

- GET /balances/{user_id}: 200 returns balance, 200 with zero amount for new user
- GET /balances/{user_id}/transactions: 200 returns list, pagination metadata
- GET /health/live: 200
- GET /health/ready: 200 healthy, 503 database error, consumer connected/disconnected reflected in messaging check

#### tests/e2e/test_consumer.py

Tests the handle_quiz_reward_message handler function with mocked BalanceService and mocked UoW. Covers:

- Valid message credits balance, service called once
- Invalid JSON raises exception (causes NACK to DLQ)
- Invalid schema raises exception (causes NACK to DLQ)
- Zero-coin event processed without error
- DB error propagates (causes NACK)
- Duplicate event does not raise (idempotent)
- IdempotencyMismatchError propagates
- Correct field deserialization from event bytes
- Empty body raises
- Consumer supervisor stops cleanly on CancelledError
- is_consumer_connected returns correct boolean based on consumer state

---

## 15. Sample Data and Manual API Testing

This section provides ready-to-use sample payloads for manually exercising the full end-to-end flow.

A sample user ID is used throughout these examples:

```
USER_ID = 11111111-1111-1111-1111-111111111111
```

### Step 1: Create a quiz with all question types

```
POST http://localhost:8002/api/v1/quizzes
Content-Type: application/json
```

```json
{
  "title": {
    "en": "Python Fundamentals",
    "de": "Python-Grundlagen",
    "es": "Fundamentos de Python",
    "ru": "Основы Python"
  },
  "description": {
    "en": "Test your knowledge of Python basics.",
    "de": "Testen Sie Ihre Python-Grundkenntnisse."
  },
  "questions": [
    {
      "type": "single_choice",
      "text": {
        "en": "Who created the Python programming language?",
        "de": "Wer hat die Programmiersprache Python erstellt?"
      },
      "payload": {
        "correct_id": "sc-opt-1",
        "options": [
          {
            "id": "sc-opt-1",
            "text": {
              "en": "Guido van Rossum",
              "de": "Guido van Rossum"
            }
          },
          {
            "id": "sc-opt-2",
            "text": {
              "en": "Linus Torvalds",
              "de": "Linus Torvalds"
            }
          },
          {
            "id": "sc-opt-3",
            "text": {
              "en": "Bjarne Stroustrup",
              "de": "Bjarne Stroustrup"
            }
          }
        ]
      }
    },
    {
      "type": "fill_gap",
      "text": {
        "en": "Python was first released in ___.",
        "de": "Python wurde zuerst im Jahr ___ veröffentlicht."
      },
      "payload": {
        "correct_answers": ["1991", "1990"]
      }
    },
    {
      "type": "multiple_choice",
      "text": {
        "en": "Which of the following are valid Python data types?",
        "de": "Welche der folgenden sind gültige Python-Datentypen?"
      },
      "payload": {
        "correct_ids": ["mc-opt-1", "mc-opt-3", "mc-opt-4"],
        "options": [
          {
            "id": "mc-opt-1",
            "text": {
              "en": "list",
              "de": "Liste"
            }
          },
          {
            "id": "mc-opt-2",
            "text": {
              "en": "array (built-in)",
              "de": "Array (eingebaut)"
            }
          },
          {
            "id": "mc-opt-3",
            "text": {
              "en": "dict",
              "de": "Wörterbuch"
            }
          },
          {
            "id": "mc-opt-4",
            "text": {
              "en": "tuple",
              "de": "Tupel"
            }
          }
        ]
      }
    },
    {
      "type": "matching",
      "text": {
        "en": "Match the Python collection type to its syntax.",
        "de": "Weisen Sie den Python-Sammlungstyp seiner Syntax zu."
      },
      "payload": {
        "pairs": [
          {
            "pair_id": "m-left-1",
            "left": {
              "en": "List",
              "de": "Liste"
            },
            "right": {
              "en": "[ ]",
              "de": "[ ]"
            },
            "right_id": "m-right-1"
          },
          {
            "pair_id": "m-left-2",
            "left": {
              "en": "Dictionary",
              "de": "Wörterbuch"
            },
            "right": {
              "en": "{ }",
              "de": "{ }"
            },
            "right_id": "m-right-2"
          },
          {
            "pair_id": "m-left-3",
            "left": {
              "en": "Tuple",
              "de": "Tupel"
            },
            "right": {
              "en": "( )",
              "de": "( )"
            },
            "right_id": "m-right-3"
          }
        ]
      }
    }
  ]
}
```

Save the quiz_id from the response. Example: 550e8400-e29b-41d4-a716-446655440000

### Step 2: Activate the quiz

```
PATCH http://localhost:8002/api/v1/quizzes/550e8400-e29b-41d4-a716-446655440000/status
Content-Type: application/json

{"is_active": true}
```

Expected response: 204 No Content.

### Step 3: Retrieve the quiz (as a client would, with locale)

```
GET http://localhost:8002/api/v1/quizzes/550e8400-e29b-41d4-a716-446655440000
Accept-Language: en
```

Verify that the response payload does not contain correct_id or correct_ids or correct_answers. The grading data must be absent.

### Step 4: Browse the catalogue

```
GET http://localhost:8002/api/v1/quizzes?limit=10&offset=0
Accept-Language: de
```

The response should contain your quiz with the German title.

### Step 5: Start an attempt

```
POST http://localhost:8002/api/v1/attempts/550e8400-e29b-41d4-a716-446655440000/start
X-User-ID: 11111111-1111-1111-1111-111111111111
```

Save the attempt_id from the response. Example: cc7a20db-1234-5678-abcd-000000000001

### Step 6: Auto-save a draft answer

You need the question_id values from the quiz detail response in Step 3. Replace them with actual UUIDs from your response.

```
PUT http://localhost:8002/api/v1/attempts/cc7a20db-1234-5678-abcd-000000000001/answers
Content-Type: application/json
X-User-ID: 11111111-1111-1111-1111-111111111111

{
  "answer": {
    "question_id": "REPLACE_WITH_QUESTION_1_UUID",
    "answer_payload": {
      "question_type": "single_choice",
      "selected_id": "sc-opt-1"
    }
  }
}
```

Expected response: 204 No Content.

### Step 7: Submit the attempt with all answers

Replace question UUIDs with your actual values from the quiz detail response.

```
POST http://localhost:8002/api/v1/attempts/cc7a20db-1234-5678-abcd-000000000001/submit
Content-Type: application/json
X-User-ID: 11111111-1111-1111-1111-111111111111

{
  "answers": [
    {
      "question_id": "REPLACE_WITH_QUESTION_1_UUID",
      "answer_payload": {
        "question_type": "single_choice",
        "selected_id": "sc-opt-1"
      }
    },
    {
      "question_id": "REPLACE_WITH_QUESTION_2_UUID",
      "answer_payload": {
        "question_type": "fill_gap",
        "answer": "1991"
      }
    },
    {
      "question_id": "REPLACE_WITH_QUESTION_3_UUID",
      "answer_payload": {
        "question_type": "multiple_choice",
        "selected_ids": ["mc-opt-1", "mc-opt-3", "mc-opt-4"]
      }
    },
    {
      "question_id": "REPLACE_WITH_QUESTION_4_UUID",
      "answer_payload": {
        "question_type": "matching",
        "pairs": [
          {"pair_id": "m-left-1", "matched_pair_id": "m-right-1"},
          {"pair_id": "m-left-2", "matched_pair_id": "m-right-2"},
          {"pair_id": "m-left-3", "matched_pair_id": "m-right-3"}
        ]
      }
    }
  ]
}
```

Expected response:

```json
{
  "attempt_id": "cc7a20db-1234-5678-abcd-000000000001",
  "score": 4,
  "total_questions": 4,
  "coins_awarded": 400,
  "question_results": [
    {"question_id": "...", "is_correct": true, "was_already_rewarded": false},
    {"question_id": "...", "is_correct": true, "was_already_rewarded": false},
    {"question_id": "...", "is_correct": true, "was_already_rewarded": false},
    {"question_id": "...", "is_correct": true, "was_already_rewarded": false}
  ]
}
```

### Step 8: Wait for balance update

The outbox worker runs every 2 seconds. After that interval, the quiz service will publish the event to RabbitMQ, and the balance service will process it.

```
GET http://localhost:8001/api/v1/balances/11111111-1111-1111-1111-111111111111
```

Expected response:

```json
{
  "user_id": "11111111-1111-1111-1111-111111111111",
  "amount": 400,
  "updated_at": "2026-03-26T12:34:56.789Z"
}
```

### Step 9: Check transaction history

```
GET http://localhost:8001/api/v1/balances/11111111-1111-1111-1111-111111111111/transactions?page=1&page_size=50
```

Expected response contains one transaction with amount 400 and a description referencing the attempt ID.

### Step 10: Test idempotency by retaking the quiz

Start a new attempt:

```
POST http://localhost:8002/api/v1/attempts/550e8400-e29b-41d4-a716-446655440000/start
X-User-ID: 11111111-1111-1111-1111-111111111111
```

Submit with all correct answers again using the new attempt_id.

In the response, all question_results will have was_already_rewarded: true and coins_awarded will be 0. The balance will not change.

### Step 11: Test submitting an already-completed attempt

Try submitting to the same attempt_id from Step 7 again:

```
POST http://localhost:8002/api/v1/attempts/cc7a20db-1234-5678-abcd-000000000001/submit
X-User-ID: 11111111-1111-1111-1111-111111111111
...
```

Expected response: 409 Conflict.

### Step 12: Test locale switching

```
GET http://localhost:8002/api/v1/quizzes/550e8400-e29b-41d4-a716-446655440000
Accept-Language: de
```

The question texts and option texts should appear in German.

```
GET http://localhost:8002/api/v1/quizzes/550e8400-e29b-41d4-a716-446655440000
Accept-Language: zh
```

Chinese is not in the quiz content. The response should fall back to English text.

---

## 16. Design Decisions and Patterns

### Domain entity separation from ORM models

The codebase maintains three distinct layers for data representation: SQLAlchemy ORM models (for database interaction), dataclass entities (domain objects with business-meaningful fields), and Pydantic DTOs (for HTTP serialization). This separation has a concrete benefit: service and repository unit tests can be written without instantiating SQLAlchemy models, without requiring a database connection, and without importing FastAPI. The GradingService tests are a perfect example: they create QuestionEntity instances directly, pass them to check_answer, and assert on a boolean. There is nothing to mock.

The use of slots=True on the dataclasses is an additional performance optimization that prevents accidental attribute addition and reduces per-instance memory overhead.

### Unit of Work pattern

The UoW encapsulates a single SQLAlchemy session and exposes typed repository attributes. Service methods open a UoW with async with self._uow, perform all operations, and commit. If any operation raises an exception, the UoW's __aexit__ calls rollback automatically. This keeps transaction boundaries visible and explicit at the service layer rather than hidden inside individual repository methods.

### Dependency injection via FastAPI Annotated types

FastAPI's dependency injection is used heavily. IUserID, ILocale, ISession, IRedis, IAttemptService, IQuizService, IQuizLocalizationService, IRewardService, IGradingService are all Annotated type aliases that carry the Depends(...) annotation. This allows test code to override any dependency with a mock by populating app.dependency_overrides before making a request, without modifying any application code.

### Correlation ID middleware

Every HTTP request receives a correlation ID from the X-Correlation-ID header (or a generated UUID if the header is absent). The ID is bound to structlog's context vars, which are thread-local (task-local in asyncio) and are merged into every log record produced during the request's lifetime. The same ID is echoed back in the X-Correlation-ID response header, allowing client-side and server-side logs to be joined.

### Pessimistic locking for concurrent submissions

The choice of SELECT ... FOR UPDATE over optimistic locking is deliberate. For the attempt submission flow, the optimistic approach (read attempt, check version, conditional update) requires either retrying the full grading computation or returning an error to the client. With pessimistic locking, the second concurrent request simply waits for the first transaction to complete, reads the now-COMPLETED status, and raises AttemptAlreadyCompletedException. The client receives a clear 409 response and no grading work is duplicated.

### JSONB for localized content and question payloads

Storing the full locale map in a JSONB column eliminates the need for a separate translations table, avoids joins on every query, and allows new languages to be added by updating content records rather than schema. The JSONB type in PostgreSQL supports indexing with GIN indexes if content-based search is ever needed. The trade-off is that the application must handle the locale extraction logic, which is centralized in QuizLocalizationService.

### Separate databases per service

quiz_db and balance_db are two entirely separate PostgreSQL instances with no cross-database references. This is a prerequisite for independent deployability: either service can be scaled, migrated, or restarted without affecting the other. The only coupling between services is the event schema defined in the shared library.

### Dead-letter queue

Failed messages (malformed JSON, schema violations, unrecoverable database errors) are negatively acknowledged with requeue=False. aio-pika routes them to the dead-letter exchange configured on the queue (via x-dead-letter-exchange), which deposits them into balance.quiz_reward.dlq. An operations team can inspect the DLQ to diagnose failures and replay messages if appropriate.

---

## 17. Known Limitations and Future Improvements

### Missing explicit exception handlers

AttemptAlreadyCompletedException inherits from ConflictException, but because Python resolves exception handlers in registration order, the ConflictException handler must be registered before the FineloBaseException handler to work correctly. ForbiddenException does not have a handler at all and falls through to the generic 500 handler. Both should receive dedicated handlers:

```python
@app.exception_handler(ForbiddenException)
async def forbidden_handler(request: Request, exc: ForbiddenException) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"error": {"code": exc.code, "message": exc.message}},
    )

@app.exception_handler(AttemptAlreadyCompletedException)
async def attempt_completed_handler(request: Request, exc: AttemptAlreadyCompletedException) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"error": {"code": exc.code, "message": exc.message}},
    )
```

### Secrets committed to source control

The .env files contain actual database credentials and should be replaced with .env.example files. In production, secrets should be injected via environment variables or a secrets manager (AWS Secrets Manager, HashiCorp Vault, Docker secrets).

### Migration container runtime pip install

The migration containers install alembic and asyncpg via pip at runtime. This should be moved to the builder stage of the Dockerfile by adding these as regular dependencies in pyproject.toml.

### No authentication or authorization

The quiz service creates quizzes, activates them, modifies questions, and starts attempts, all from the same routes without any role differentiation. In production, content management endpoints (POST /quizzes, PATCH /quizzes/{id}/status, POST /quizzes/{id}/questions) should require an admin or editor role. Authorization is assumed to be handled by an API gateway or auth middleware upstream. This is documented here as a known gap for a production deployment.

### No integration tests touching a real database

The current test suite uses mocked repositories and services throughout. While this is valuable for fast unit tests, adding a set of integration tests that run against a real PostgreSQL and Redis instance (using testcontainers-python or a Docker Compose test profile) would give confidence that the SQL queries, Alembic migrations, and cache invalidation logic work correctly end-to-end.

### Outbox worker retry backoff

The outbox worker currently increments the attempts counter on failure but does not implement backoff for retries. A message that fails to publish will be retried on every poll cycle (every 2 seconds) indefinitely. Adding a maximum attempts threshold and an exponential backoff between retries would prevent a poisoned event from blocking other events in the batch.

### Question order rebalancing not implemented

When a question is deleted, the order_index values of the remaining questions are not rebalanced. For example, if questions at indices 0, 1, 2 exist and index 1 is deleted, the remaining questions will have indices 0 and 2 with a gap. This does not cause incorrect behavior because sorting by order_index still produces a consistent order, but it may confuse content editors who expect contiguous indices.

### Balance debit not implemented

The TransactionType enum includes DEBIT and the constraint CHECK (amount > 0) applies to all transaction types, but no service method or route implements debiting. If the platform ever needs to charge coins for a service, a debit method would need to be added to BalanceService, with appropriate InsufficientBalanceException handling and an optimistic or pessimistic guard against negative balance.

### Kafka support is wired but not deployed

The shared library includes KafkaPublisher and KafkaConsumer, and the messaging __init__.py exports them. The docker-compose.yml does not include a Kafka broker. If the platform migrates to Kafka, both the quiz service (publisher) and the balance service (consumer) would need only their configuration changed, and the shared library already provides the correct abstraction. No application code changes would be required.

---
