# Quiz Service Analysis & Workflow Documentation

This document describes the internal workflows of the `quiz_service` and proposed improvements for configuration management.

## 1. Core Workflows

### 1.1. How we check that user not already answered
Correct answers are rewarded with coins. To prevent double rewarding for the same question across multiple attempts:
1. When an attempt is submitted, the system identifies all correctly answered questions.
2. It queries the `user_rewarded_questions` table using `AttemptRepository.get_already_rewarded_question_ids(user_id, question_ids)`.
3. Only questions NOT present in this set are considered for new rewards.
4. These new questions are then inserted into `user_rewarded_questions` atomically within the submission process.

### 1.2. How grading works
The `GradingService` is a stateless service that takes a `QuestionEntity` and a `answer_payload`.
- It uses a strategy-like pattern to check correctness based on `QuestionType` (Single Choice, Multiple Choice, Fill Gap, Matching).
- It handles normalization (e.g., lowercasing and trimming strings for `fill_gap`).

### 1.3. How consumer works (Transactional Outbox)
The service uses the **Transactional Outbox Pattern**:
1. Business logic (updating attempt, recording rewards) and event creation are performed in the same database transaction.
2. The event is written to the `outbox_events` table.
3. An external **Outbox Worker** (likely a separate process or service) polls this table, publishes events to RabbitMQ (using the specified `routing_key`), and marks them as published.
4. This ensures "at-least-once" delivery and avoids distributed transaction issues.

---

## 2. Configuration & Dynamic Rewards

### 2.1. Current State
Currently, `COINS_PER_CORRECT_ANSWER` and `QUIZ_REWARD_ROUTING_KEY` are hardcoded in `AttemptService`. This is inflexible and requires code changes for any adjustment.

### 2.2. Proposed Improvement (Static/Env)
Move these values to `src/config/project.py` and sync them with `.env`. This allows for easy environment-specific configuration without code changes.

### 2.3. Dynamic Rewards (Future-Proofing)
To handle dynamic rewards (different coins per user, per quiz, or per level):
- **Option A (Per Quiz)**: Add a `reward_coins` field to the `Quiz` model. This allows different quizzes to have different values.
- **Option B (Rule-based)**: Integrate with a **Rule Engine** (like the one used in the booking service) to determine coins based on user profile, quiz difficulty, or streak.
- **Option C (Database Config)**: Store these in a `GlobalSettings` or `RewardPolicy` table in the database, which can be modified via an admin API.

**Recommendation**: For now, move to `.env` for basic flexibility. If the requirement for per-quiz rewards arises, Option A is the most straightforward architectural path.


EXAMPLE:
{
  "answers": [
    {
      "question_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
      "answer_payload": {
        "selected_id": "a"
      }
    },
    {
      "question_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
      "answer_payload": {
        "answer": "Satoshi Nakamoto"
      }
    },
    {
      "question_id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
      "answer_payload": {
        "selected_ids": ["a", "b", "d"]
      }
    },
    {
      "question_id": "dddddddd-dddd-dddd-dddd-dddddddddddd",
      "answer_payload": {
        "pairs": [
          {
            "pair_id": "p1",
            "matched_pair_id": "p1"
          },
          {
            "pair_id": "p2",
            "matched_pair_id": "p2"
          }
        ]
      }
    }
  ]
}
