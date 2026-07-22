# Step 66C.4-BE1-R — Independent Review Test / Reproduction Record

> **Reproduction evidence gathered by a fresh, independent review session. Every result below was
> produced by the reviewer re-running the check, not quoted from the BE1 implementation report. No
> implementation file was modified. No shared database was touched. No deployment.**

**Marker: `STEP66C4_BE1_INDEPENDENT_REVIEW_VERIFY: PASS`** (review process complete)
**Technical result: `BE1_TECHNICAL_VERDICT: REMEDIATION_REQUIRED`**

## Environment

```text
Reviewed commit:  d2467f5   Main: e03c22d   Review branch: review/66c4-be1-technical-security-migration
Worktree:         separate review worktree (implementation worktree untouched)
Database:         isolated ephemeral test PostgreSQL 16.14 (Debian), created for this review only and
                  destroyed at the end. The shared test database and its container were NOT used and
                  NOT migrated.
Baseline applied: migrations 029 -> 030 -> 031, plus 031 reapply, 031 down, 031 up again.
```

## 5.1 Transaction-crossing-deadline — FAILED (blocking)

```text
Procedure: seed status='open', due_at = now()+3s; open an explicit transaction on a separate
connection BEFORE due_at; hold it open 5 s so DB time passes due_at; execute the exact committed CAS
inside that same transaction.

due_at              = 2026-07-22 08:58:28.941605+00
txn now()           = 2026-07-22 08:58:25.993359+00   (transaction_timestamp -- txn began before due_at)
statement_timestamp = 2026-07-22 08:58:25.996215+00
clock_timestamp     = 2026-07-22 08:58:25.996219+00

--- 5 s later, same open transaction ---
now()               = 2026-07-22 08:58:25.993359+00   FROZEN (unchanged)
statement_timestamp = 2026-07-22 08:58:31.001742+00   advanced
clock_timestamp     = 2026-07-22 08:58:31.001749+00   advanced

CLAIM RESULT inside cross-deadline txn : SUCCEEDED (row claimed)
answered_at written                    : 2026-07-22 08:58:25.993359+00 (backdated 5.008 s)
committed status                       : answered

CONTROL (autocommit, today's real call path, claim 4 s after a 2 s deadline):
                                       : rejected (correct)
```

Conclusion: the deadline is evaluated at transaction-start time, not claim-statement time. Today's
call path is safe by accident of shape; the binding contract (§11.3 same-transaction outbox insert)
requires BE2 to introduce the wrapping that breaks it. **Deadline verdict: REMEDIATION_REQUIRED.**

## 5.2 `due_at IS NULL` compatibility — PASS

```text
information_schema: operator_clarification_requests.due_at is_nullable = NO
INSERT ... due_at NULL -> NotNullViolationError (rejected by the schema)
(NULL::timestamptz > now()) => NULL   (three-valued logic: not TRUE)
Simulated legacy NULL row on a scratch table, real CAS predicate:
  rows matching (status='open' AND answered_at IS NULL AND due_at > now()) = 0
Migration history: only migration 030 creates operator_clarification_requests, and it declares
  due_at TIMESTAMPTZ NOT NULL. No earlier schema version of the table exists.
```

Conclusion: a NULL `due_at` row is structurally impossible, not merely absent today. Had one existed,
it would have been permanently locked out and mis-reported as `expired` — recorded as the reason to
add a `NOT NULL` regression assertion during remediation.

## 5.3 Migration up / down / reapply — PASS

```text
031 up       0.015 s     031 reapply  0.003 s (idempotent, no error, no duplicate object)
031 down     succeeds    031 up again succeeds, schema identical (deterministic)
Six lifecycle columns present and is_nullable=YES; resume_dispatched_at absent
Outbox table + 4 indexes + UNIQUE + 4 CHECKs present
After down: all six columns gone, to_regclass('clarification_lifecycle_outbox') IS NULL, both partial
  indexes gone, chk_ocr_resume_authorized_requires_eligible gone; due_at/status/answered_at/
  reminder_at and all pre-existing indexes survive; operator_tasks/task_messages untouched
Seeded-before-migration rows: status, answered_at, due_at, reminder_at unchanged; new columns NULL
relfilenode before=16461, after down+up=16461  => NO TABLE REWRITE
Lock behaviour: ADD COLUMN (nullable, no default) is catalog-only ACCESS EXCLUSIVE (PG11+);
  CREATE INDEX is not CONCURRENT (informational)
pg_attribute dropped-column tombstones after 2 down/up cycles: 12 (informational)
old code + migrated schema: safe (all additive/nullable, old CAS still matches)
new code + migrated schema: verified (15 BE1 + 229 regression tests pass)
```

## 5.4 Concurrent answer CAS — PASS

```text
Two independent asyncpg connections, explicit transactions:
  A executes the CAS and holds the row lock -> A won
  B executes the same CAS concurrently      -> B BLOCKED while A held the lock (verified: not done)
  A commits -> B re-evaluates -> B lost (returned no row)   [correct]
Exactly one winner. No lost update, no double-answer.
```

Post-failure 409 re-classification (`answer_clarification`), analysed for TOCTOU:

```text
Loser-of-a-concurrent-answer misclassified as "expired"? NO. The loser blocks on the row lock until
  the winner COMMITS, so the subsequent re-read always observes status='answered'.
Deadline failure misclassified as "already answered"?    NO. A deadline loss leaves status='open',
  which the classifier maps to invalid_state_for_answer:expired.
Deadline loss racing a future timeout worker?            SAFE. If the worker materialises 'expired'
  first, the classifier emits the same invalid_state_for_answer:expired string.
Residual: current is None (row deleted) -> reported as clarification_already_answered (LOW, L-3).
Residual: the same wrapping-transaction change that breaks B-1 would also make the re-read
  non-atomic with the claim. Remediation must re-check this classifier at BE2.
```

## 5.5 Outbox durability capability matrix — FOUNDATION_REMEDIATION_REQUIRED_BEFORE_MERGE

Full matrix in `docs/contracts/66c4-reminder-expiry-controlled-resume/be1-outbox-foundation-
sufficiency-review.md`. Summary of the classifications:

```text
SUPPORTED_BY_CURRENT_SCHEMA        pending ordering; published terminal state; dead terminal STATE;
                                   stuck-event detection; reconciliation metrics; idempotency;
                                   transaction atomicity
SUPPORTED_WITHOUT_SCHEMA_CHANGE    multiple workers; safe claim; worker-crash recovery; bounded retry;
                                   operator replay (mechanically)
REQUIRES_SCHEMA_CHANGE             persisted retry schedule (available_at/next_attempt_at); retry
                                   backoff; bounded safe error diagnosis (last_error); dead-state
                                   TIMESTAMP (dead_at)
UNRESOLVED                         operator-replay governance (no replay actor/trail defined; §11.3
                                   defers to "existing DLQ replay tooling" without a route)

Missing columns assessed: available_at/next_attempt_at MISSING (required); published_at PRESENT;
  dead_at MISSING (required); last_error MISSING (required); claim owner MISSING (not required under
  transaction-scoped FOR UPDATE SKIP LOCKED); claim/lease expiry MISSING (same condition).
```

## 5.6 No-live-producer verification — PASS

```text
git grep -n for clarification_lifecycle_outbox | lifecycle_outbox | LifecycleOutbox | insert.*outbox
| enqueue.*outbox, every hit classified:

  definition          shared/sdk/tasks/lifecycle_outbox.py                    (6 hits)
  migration           migrations/031_*.sql, 031_*_down.sql                    (9 hits)
  test                tests/test_step66c4_be1_*.py, tests/test_step66c4_planning_*.py (30 hits)
  verifier/script     scripts/verify_step66c4_be1_*.py, verify_step66c4_planning_*.py (10 hits)
  documentation       docs/**, source/progress.md                             (all remaining hits)

  runtime producer        : 0
  runtime outbox write    : 0
  relay loop              : 0
  scheduler / poller loop : 0
  startup activation      : 0

git diff --name-only origin/main -- shared/sdk/audit shared/sdk/event_bus apps/retry-scheduler
  apps/communication-gateway  -> EMPTY (existing audit/event transport unchanged)
git diff --name-only origin/main -- infra helm k8s .github/workflows -> EMPTY
```

## 5.7 Security probes — no critical, no high

```text
assert_safe_outbox_payload probes (reviewer-run):
  {'meta': {'answer': '<raw body>'}}      -> ACCEPTED   (nested bypass -- MEDIUM M-1)
  {'items': [{'token': 'ghp_...'}]}       -> ACCEPTED   (nested bypass -- MEDIUM M-1)
  {'answer_body': 'raw body text'}        -> ACCEPTED   (exact-match deny list -- MEDIUM M-1)
  {'question_text': 'raw question'}       -> ACCEPTED   (exact-match deny list -- MEDIUM M-1)
  {'ANSWER': 'x'}                         -> rejected   (case handled correctly)
grep for logger/logging/print in the BE1 modules -> none (no payload can leak to logs)
All BE1 SQL uses asyncpg $-parameters; clarification ids coerced through uuid.UUID()
Outbox FKs are NO ACTION -> deleting a clarification with outbox rows is refused (evidence protected)
Masking: no internal IP, SSH alias or OS username appears in any committed file (BE1 or this review)
```

## 6. Independent test/verifier/tooling reruns

```text
python scripts/verify_step66c4_be1_data_model_deadline_outbox.py
  -> STEP66C4_BE1_DATA_MODEL_DEADLINE_OUTBOX_VERIFY: PASS

BE1_TEST_DATABASE_URL=<isolated ephemeral test Postgres> pytest tests/test_step66c4_be1_*.py -q
  -> 15 passed in 1.79s   (integration tests RUN, not skipped)
pytest tests/test_step66c4_be1_*.py -q     (no DSN)
  -> 10 passed, 5 skipped (silent skip -- gap G-1)

pytest tests/ -q -k "66c or workroom or clarification or task_api"
  -> 229 passed, 5 skipped, 4724 deselected in 156.42 s, 0 failed

ruff check  <5 BE1 files>  -> All checks passed
black --check <5 BE1 files> -> 5 files unchanged
git diff --check origin/main -> clean
Repo-wide ruff (8) / black (30) / mypy (1) failures are PRE-EXISTING in files BE1 never touched
  (tests/test_alert_receiver_auth.py, tests/test_incident_*, agents/design-review-agent/**).
```

## Scope confirmation

```text
git diff --name-only origin/feature/66c4-be1-lifecycle-outbox-foundation...HEAD
  -> only review artifacts under docs/contracts/**, docs/handoffs/**, docs/test/**, docs/stages/**,
     scripts/verify_step66c4_be1_independent_review.py,
     tests/test_step66c4_be1_independent_review.py, source/progress.md
  -> ZERO implementation, migration, app, service, infra, helm, k8s, frontend or workflow paths.
```

## Statement

Independent review reproduction record only. No implementation change. No migration change. No merge.
No deployment. No shared database migrated. No scheduler or relay activated. No dispatch/resume. No
external notification. `production_executed_true_count` remains 0. Product Owner review required.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
