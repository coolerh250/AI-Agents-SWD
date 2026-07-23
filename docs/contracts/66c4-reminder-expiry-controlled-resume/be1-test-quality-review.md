# Step 66C.4-BE1-R — Test Quality Independent Review

> **Independent review artifact. No test file under review was modified. All suites were re-run by
> the reviewer against an isolated ephemeral test PostgreSQL 16.**

**Test-quality verdict: PASS_WITH_GAPS** (the gaps are test coverage, not test correctness; the
behaviour gaps they failed to catch are recorded as blocking findings in the deadline and outbox
reviews).

## Reproduced results

```text
python scripts/verify_step66c4_be1_data_model_deadline_outbox.py
  -> STEP66C4_BE1_DATA_MODEL_DEADLINE_OUTBOX_VERIFY: PASS   (22 checks, all green)

BE1_TEST_DATABASE_URL=<isolated ephemeral test Postgres>
python -m pytest tests/test_step66c4_be1_data_model_deadline_outbox.py -q
  -> 15 passed in 1.79s        (integration tests RUN, not skipped)

python -m pytest tests/test_step66c4_be1_data_model_deadline_outbox.py -q   (no DSN)
  -> 10 passed, 5 skipped

python -m pytest tests/ -q -k "66c or workroom or clarification or task_api"
  -> 229 passed, 5 skipped, 4724 deselected in 156.42s     (0 failed)

ruff check <the five BE1 files>      -> All checks passed
black --check <the five BE1 files>   -> 5 files unchanged
git diff --check origin/main         -> clean (no whitespace/conflict artefacts)
```

Repository-wide `ruff check .` (8 errors), `black --check .` (30 files) and `mypy .` (a duplicate
module error under `agents/design-review-agent/`) all fail, but every offending file is pre-existing
and untouched by BE1 (`tests/test_alert_receiver_auth.py`, `tests/test_incident_*`, etc.). This is
baseline repository noise, not a BE1 regression.

## Assessment against the required criteria

| Criterion | Result |
| --- | --- |
| Postgres tests do not silently skip | **PARTIAL.** They are `skipif`-gated on `BE1_TEST_DATABASE_URL` and skip silently when it is unset — verified: 5 skipped. This matches the repo's existing stack-test convention and the DSN must not be a shared DB, so gating is right; but nothing in the verifier asserts that they were ever RUN, so a green verifier does not imply real-Postgres evidence. See gap G-1. |
| Concurrency tests use independent connections | **YES.** `WorkroomStore.claim_clarification_answer` calls `self._connect()` per invocation, so the two `asyncio.gather` claims genuinely use two separate asyncpg connections. |
| The boundary test genuinely crosses the DB deadline | **NO — see gap G-2.** |
| The exact-boundary test is not a tautology | **NO — see gap G-3.** |
| Tests do not rely only on a Python clock | **YES for the Postgres tests** (`due_at` is computed with `now() + interval` inside the database, and the CAS compares DB time to DB time; no Python clock is involved). The API-level test uses an in-memory store with a Python clock, but it is explicitly a 409-shape test, not a deadline test. |
| Cleanup is deterministic | **YES, with a caveat — see gap G-4.** Each Postgres test begins with an unconditional `DROP TABLE ... CASCADE` and rebuilds 029/030/031, so runs are independent of each other and of ordering. |
| Migration down / reapply actually execute | **YES.** `test_pg_migration_creates_schema_and_rolls_back` really executes the up script twice and the down script once against the database and asserts on `information_schema` / `pg_indexes` / `to_regclass`, not on file text. Independently re-verified. |
| Affected-suite results are reproducible | **YES.** 229 passed / 0 failed, reproduced independently. |

## Gaps

### G-1 — a green verifier does not prove the Postgres tests ran

The verifier is purely static and never executes pytest, and the integration tests skip silently
without a DSN. A CI run with no `BE1_TEST_DATABASE_URL` would report
`STEP66C4_BE1_DATA_MODEL_DEADLINE_OUTBOX_VERIFY: PASS` with 10/15 tests and zero real-database
evidence. Recommendation: have the verifier (or the test record) require the integration run's
pass count, or emit an explicit "integration evidence: skipped" warning.

### G-2 — there is no transaction-crossing-deadline test, and its absence is exactly why the deadline defect survived

No committed test executes the answer CAS inside an explicit transaction that began before `due_at`.
Every deadline test runs through `WorkroomStore`, which is autocommit — the one shape in which
`now()` happens to behave correctly. The reviewer's own reproduction (see
`be1-deadline-semantics-review.md`) shows the claim SUCCEEDS in the cross-deadline transaction shape.
This is the single most important missing test in the suite.

### G-3 — the "exact boundary" case is a near-tautology

`test_pg_deadline_cas_future_past_boundary` seeds `due_offset_hours=0`, so `due_at` is set to `now()`
at INSERT time and the claim runs milliseconds later with `now() > due_at`. It therefore re-tests the
past-deadline branch already covered two lines above, and never exercises `now() == due_at`. The
test's own comment admits this ("due_at was set to now() at insert; a later claim has now() > due_at").
A genuine equality test would pin `due_at` to a captured DB timestamp and compare against that same
timestamp. The exclusive-bound behaviour is correct (independently confirmed), but it is asserted by
inspection, not by this test.

### G-4 — the Postgres fixtures are unconditionally destructive with no ephemerality guard

Every integration test opens with
`DROP TABLE IF EXISTS clarification_lifecycle_outbox, operator_clarification_requests, task_messages,
operator_tasks CASCADE;`. If `BE1_TEST_DATABASE_URL` were ever pointed at a shared test database, the
suite would destroy four tables and all their data without warning. The docstring says "isolated,
ephemeral" but nothing enforces it. Recommendation: assert on a required marker (a dedicated database
name prefix, or a sentinel table) before the first DROP.

### G-5 — no `due_at IS NULL` / legacy-compatibility test

There is no test asserting `due_at` remains `NOT NULL`. The behaviour is safe today because migration
030 declares the column `NOT NULL` (independently verified), but nothing would fail if a future
migration relaxed it, and the CAS would then permanently lock such rows out.

### G-6 — the concurrency test is timing-dependent rather than barrier-synchronised

`test_pg_concurrent_answer_exactly_one_wins` fires two claims through `asyncio.gather` with no
synchronisation point, so it does not guarantee genuine overlap; it would still pass if the two
claims serialised completely. The reviewer independently ran the stronger form — connection A holds
an open transaction with the row locked while connection B's claim blocks, then A commits — and
confirmed B blocks and then correctly loses. The property holds; the committed test just proves it
more weakly than it appears to.

## Statement

Independent test-quality review artifact only. No test under review was modified. No implementation
change. No deployment. No merge.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
