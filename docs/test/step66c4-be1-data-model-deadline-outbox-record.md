# Step 66C.4-BE1 — Test / Verification Record

Marker: `STEP66C4_BE1_DATA_MODEL_DEADLINE_OUTBOX_VERIFY: PASS`

Backend foundation slice for Step 66C.4: additive lifecycle schema, deadline CAS, and a
disabled-by-default transactional-outbox foundation on branch
`feature/66c4-be1-lifecycle-outbox-foundation`. Implementation complete, pending independent review
(Step 66C.4-BE1-R). Not merged, not deployed.

## Real-Postgres execution environment

```text
An ISOLATED, EPHEMERAL Postgres 16 container (throwaway, separate from the shared aiagents
database) was used for the integration tests. The migration chain (uuid-ossp + 029 + 030 + 031) was
applied to a fresh database, scenarios were run, and 031_down was applied. The container was torn
down afterward. No shared test/staging/production runtime was migrated. The DSN was supplied via the
BE1_TEST_DATABASE_URL environment variable (local only; never committed).
```

## Migration tests (real Postgres)

```text
test_pg_migration_creates_schema_and_rolls_back:
  - migration up succeeds; six lifecycle fields exist and are nullable; outbox table exists;
    idx_ocr_reminder_due / idx_ocr_expiry_due / idx_clo_pending_created present; resume_dispatched_at
    absent; reapply is idempotent; down removes the six columns + outbox; pre-existing due_at/status
    survive.
test_pg_existing_rows_remain_intact_after_migration:
  - a row created BEFORE the migration remains readable/unmutated after it (status/answered_at
    unchanged; new columns NULL).
```

## Deadline CAS tests

```text
test_answer_cas_sql_enforces_authoritative_deadline (static): predicate `due_at > now()` +
  `answered_at IS NULL` + `status='open'` present in the CAS.
test_pg_deadline_cas_future_past_boundary (real Postgres):
  - future due_at -> claim succeeds; past due_at (row still 'open') -> claim fails, row stays 'open';
    exact boundary -> fails (exclusive bound); already-answered -> fails.
test_pg_concurrent_answer_exactly_one_wins (real Postgres): two concurrent claims -> exactly one
  winner.
test_past_deadline_answer_returns_409_expired (API): 409 invalid_state_for_answer:expired.
test_within_deadline_answer_succeeds (API): 200; success schema unchanged.
No exactly-once event delivery is claimed; the CAS guarantees a single state claim only.
```

## Outbox foundation tests

```text
test_outbox_payload_guard_rejects_prohibited_keys / _rejects_oversize / _accepts_safe_minimal.
test_outbox_event_type_allowlist.
test_outbox_module_has_no_live_producer_import (static: no runtime caller).
test_pg_outbox_transaction_atomicity_and_idempotency (real Postgres): transaction rollback removes
  the row; commit persists exactly one; duplicate idempotency_key raises UniqueViolationError.
```

## Regression tests

```text
Step 66C.1/66C.2/66C.3 + answered-twice + clarification flow suites: 101 passed.
Broad affected-area run (-k "workroom or task_api or clarification or audit or 66c or answered"):
  637 passed, 15 skipped, 0 failed.
```

## Verifier / quality gates

```text
python scripts/verify_step66c4_be1_data_model_deadline_outbox.py -> PASS
pytest tests/test_step66c4_be1_data_model_deadline_outbox.py     -> 15 passed (with ephemeral DSN)
ruff check .            -> clean (BE1 files)
black --check .         -> clean (BE1 files)
mypy (BE1 modules)      -> clean
git diff --check        -> clean
git status --short      -> clean (after commit)
```

## Secret scan

```text
python scripts/run_local_secret_scan.py -> critical=0, high=0, informational=100 (baseline,
  unchanged).
```

## Local Artifact Reconciliation

```text
No Windows absolute path, local username, Documents/Codex path, .tools/, or unrelated proposal
committed. The test DSN (with the ephemeral host/port) lived only in a local environment variable
and is not present in any committed file.
```

## No-deployment verification

```text
Shared test deployment: NO. Staging deployment: NO. Production deployment: NO.
Runtime migration execution (shared): NO (only isolated ephemeral test Postgres).
Scheduler activated: NO. Outbox relay activated: NO. Existing producer switched: NO.
Workflow dispatched: NO. Workflow resumed: NO. External notification: NO.
production_executed_true_count: 0 / unchanged.
```

## Statement

Test/verification record only. No scheduler activated. No outbox relay activated. No existing
producer switched. No dispatch/resume. No external notification. No shared-runtime migration. No
deployment. No production/external action. Independent review required before BE2/merge/deploy.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->

<!-- STEP66C4_BE1_DATA_MODEL_DEADLINE_OUTBOX_VERIFY: PASS -->
