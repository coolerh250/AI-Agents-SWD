# Step 66C.4-BE1-R1 Test and Verification Record

> **Test record only. No shared test, staging or production deployment. No shared database was
> migrated. All PostgreSQL work ran against an isolated ephemeral PostgreSQL 16 container created
> for this stage and destroyed afterwards.**

## Markers

```text
STEP66C4_BE1_R1_REMEDIATION_VERIFY: PASS
STEP66C4_BE1_R1_PG_EVIDENCE: PASS
STEP66C4_BE1_DATA_MODEL_DEADLINE_OUTBOX_VERIFY: PASS
```

Neither R1 marker is a technical verdict. `BE1_TECHNICAL_VERDICT` remains
`REMEDIATION_REQUIRED` as set by the independent Step 66C.4-BE1-R reviewer, and only the
independent Step 66C.4-BE1-R1-R closure reviewer may change it.

## Mandatory PostgreSQL evidence

```text
Environment: isolated ephemeral PostgreSQL 16 container, created for this stage on the internal
  test runtime, bound to a dedicated port, database name step66c4_be1r1, destroyed afterwards.
  The shared test database was never connected to and never migrated.
Opt-in:      STEP66C4_ALLOW_DESTRUCTIVE_PG_TESTS=1 (fail-closed guard satisfied)

mandatory PostgreSQL tests: 0 skipped, 0 failed
tests/test_step66c4_be1_r1_remediation.py            -> 44 passed, 0 skipped
tests/test_step66c4_be1_data_model_deadline_outbox.py -> 15 passed, 0 skipped
combined                                              -> 59 passed, 0 skipped, 0 failed
```

Without a DSN the same suites report 45 passed / 14 skipped. That state is reported as
"PostgreSQL evidence unavailable" and is NOT a complete technical pass; the verifier emits
`STEP66C4_BE1_R1_PG_EVIDENCE` separately from the static marker for exactly this reason.

## B-1 deadline evidence

Negative control, proving the regression test is not vacuous -- the same cross-deadline scenario
was executed against BOTH predicates on the ephemeral database:

```text
Scenario: due_at = statement_timestamp() + 3s; BEGIN before due_at; pg_sleep(4); then claim.

OLD  due_at > now()                  -> claim SUCCEEDED (defect reproduced), answered_at backdated
NEW  due_at > statement_timestamp()  -> claim rejected, answered_at NULL, status 'open'
```

```text
test_pg_transaction_crossing_deadline_is_rejected      PASS  (MANDATORY, not skipped)
test_pg_strict_boundary_equality_is_rejected           PASS
test_pg_answered_at_is_statement_time_not_transaction_start  PASS
test_pg_due_at_remains_not_null                        PASS
test_canonical_contract_records_correct_now_semantics   PASS
test_answer_cas_uses_statement_timestamp_for_predicate_and_answered_at  PASS
```

## Concurrency evidence

```text
test_pg_concurrent_answer_with_barrier_exactly_one_wins  PASS
  Two independent asyncpg connections synchronised by asyncio.Barrier(2); both are provably ready
  before either issues its UPDATE. Exactly one winner; final state 'answered' with answered_at set.
test_pg_loser_blocks_until_winner_commits_then_reads_final_state  PASS
  The loser is asserted to be STILL BLOCKED after 1.0s while the winner holds its uncommitted row
  lock; after the winner commits the loser returns None and reads the authoritative final state.
  No reliance on incidental timing.
```

## Migration evidence

```text
test_pg_migration_up_down_reapply_is_deterministic  PASS
  Seeded a representative row on 029+030 BEFORE applying 031.
  up applied; relfilenode of operator_clarification_requests UNCHANGED -> no table rewrite.
  Existing row byte-identical across up, down and reapply -> no destructive backfill,
  no legacy row mutation.
  available_at NOT NULL; dead_at and last_error nullable.
  chk_clo_last_error_bounded and chk_clo_status_timestamps present.
  idx_clo_pending_available, idx_clo_pending_created, idx_clo_dead_at present.
  down removed ONLY BE1 objects; due_at and status survived.
  reapply produced an identical column/type/nullability fingerprint.
test_pg_migration_creates_schema_and_rolls_back (BE1 suite)  PASS
```

## Outbox durability evidence

```text
test_pg_outbox_durability_semantics  PASS
  available_at persisted on insert; row immediately claim-eligible.
  A future available_at makes the pending row NOT claim-eligible (persisted backoff works).
  Transient-failure update persists attempts, a future available_at and a bounded last_error.
  dead records dead_at with published_at NULL; published records published_at with dead_at NULL.
  published + dead simultaneously -> CheckViolationError (coherence constraint).
  last_error above the bound -> CheckViolationError at the DB, ValueError at the repository.
  Replay mapping dead -> pending preserves attempts and the idempotency_key.
test_pg_outbox_insert_is_atomic_with_state_mutation  PASS
  Rollback leaves neither the state change nor the outbox row; commit persists both.
  Duplicate idempotency_key -> UniqueViolationError.
```

## Payload safety evidence

```text
test_payload_allowlist_rejects_bypass_attempts  PASS (12 parametrised probes, all rejected)
  {"meta": {"answer": ...}}, {"items": [{"token": ...}]}, {"answer_body": ...},
  {"question_text": ...}, {"TOKEN": ...}, {"unknown_key": ...}, {"answer": ...},
  nested dict value, list value, float value, {"clarification_id": ...}, {"task_id": ...}
test_payload_allowlist_rejects_oversized_payload   PASS
test_payload_allowlist_rejects_unknown_event_type  PASS
test_payload_allowlist_accepts_contract_keys       PASS
test_payload_error_messages_never_include_the_value  PASS
```

## Fixture safety evidence

```text
test_destructive_guard_requires_opt_in                     PASS
test_destructive_guard_refuses_shared_database_names       PASS (6 parametrised names, all refused)
test_destructive_guard_refuses_unconventional_name         PASS
test_destructive_guard_refuses_unparseable_and_empty       PASS
test_destructive_guard_allows_isolated_ephemeral_name      PASS
The guard is fail-closed: any failed or unevaluable check refuses the DSN rather than dropping.
No DSN or credential is committed to the repository.
```

## Disabled-foundation evidence

```text
test_no_relay_scheduler_or_live_producer_exists  PASS
Live producer callers: 0. Runtime outbox writes: 0. Relay loops: 0. Scheduler loops: 0.
Startup activation: 0.
git grep confirmation: the only references to lifecycle_outbox / clarification_lifecycle_outbox
  outside the module itself are in tests, docs, migrations and the verifiers.
Paths unchanged relative to main: shared/sdk/audit/**, shared/sdk/event_bus/**,
  apps/retry-scheduler/**, apps/communication-gateway/**, frontend/**, infra/**, helm/**, k8s/**,
  .github/workflows/**.
```

## Regression suites

```text
pytest tests/ -k "66c or workroom or clarification or task_api or task_rbac or audit_projection"
  -> 265 passed, 14 skipped, 0 failed (2m14s)
  The 14 skips are the PostgreSQL-gated tests in that run (no DSN exported); they are executed
  with 0 skips in the mandatory PostgreSQL run recorded above.
```

## Quality gates

```text
Affected files (7): shared/sdk/tasks/lifecycle_outbox.py, shared/sdk/tasks/workroom_store.py,
  tests/step66c4_pg_safety.py, tests/test_step66c4_be1_r1_remediation.py,
  tests/test_step66c4_be1_data_model_deadline_outbox.py,
  scripts/verify_step66c4_be1_r1_remediation.py,
  scripts/verify_step66c4_be1_data_model_deadline_outbox.py

ruff check <affected files>   -> All checks passed
black <affected files>        -> formatted; re-check clean
mypy shared/sdk/tasks/lifecycle_outbox.py shared/sdk/tasks/workroom_store.py
                              -> Success: no issues found in 2 source files
git diff --check              -> clean
git status --short            -> only intended R1 paths
```

### Pre-existing repository-wide issues (NOT introduced by R1)

```text
ruff check .        -> 8 errors, all in files untouched by BE1/BE1-R1
                       (tests/test_alert_receiver_auth.py and similar pre-existing suites)
black --check .     -> 30 files would be reformatted, none of them BE1/BE1-R1 files
mypy .              -> a duplicate-module error under agents/design-review-agent/ (pre-existing)

These counts are IDENTICAL to the baseline recorded independently by the Step 66C.4-BE1-R reviewer
(8 ruff / 30 black) before any R1 change, which is the evidence that R1 introduced none of them.
Affected-file clean is reported separately above and is NOT presented as repo-wide clean.
```

## Secret and masking scan

```text
Secret-like patterns in R1 files: none. The one sentinel string in the payload test is synthetic,
  deliberately not credential-shaped, and exists to assert that the guard never echoes a VALUE.
No DSN, password, token or credential is committed.
Masking rule: no internal IP, SSH alias or OS username appears in any file ADDED or MODIFIED by
  this stage. Pre-existing occurrences in source/progress.md date from earlier stages and were not
  added or extended here. Records use the neutral label "isolated ephemeral test PostgreSQL 16".
```

## Statement

Test record only. No scheduler implemented or activated. No outbox relay implemented or activated.
No live producer cutover. No runtime outbox write. No resume endpoint, authorization, dispatch or
workflow resume. No audit/event transport change. No external notification. No shared test,
staging or production deployment. No shared database migrated. No production or external action.
production_executed_true_count: 0 / unchanged. No merge.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
