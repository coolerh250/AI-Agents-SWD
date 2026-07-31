# Step 66C.4-BE3-RA-1A — Migration Rehearsal Test & Validation Record

> **Test record. NOT applied to any shared, test, staging, or production database. All PostgreSQL
> work ran on an isolated ephemeral container, destroyed afterward. NOT FOR MERGE / NOT
> deployed / NOT activated.**

## Marker

```text
STEP66C4_BE3_RA1_MIGRATION_REHEARSAL_VERIFY: PASS
```

## Environment

```text
Runtime:      internal test runtime (isolated ephemeral PostgreSQL 16 container on a dedicated
              port), created for this run and destroyed afterward. Isolated DB name
              step66c4_ra1_migration_rehearsal (fail-closed guard; not shared).
Guard opt-in: STEP66C4_ALLOW_DESTRUCTIVE_PG_TESTS=1 with an isolated DSN (never committed).
Worktree:     detached at commit 18f11fe (Step 66C.4-BE3-RA-P) with the uncommitted RA-1A files
              overlaid; removed after the run. The shared aiagents-test stack was NOT running
              before this stage and was NOT started by it (only the ephemeral container + an
              unrelated pre-existing monitoring container were present throughout).
```

## Results

### New: RA-1A migration rehearsal (real PostgreSQL 16)

```text
tests/test_step66c4_be3_ra1_migration_rehearsal.py -> 12 passed / 0 skipped / 0 failed
```

Coverage, matching every §17-mandated scenario:

- **Up rehearsal, stepwise (`test_pg_up_rehearsal_all_five_migrations_stepwise`):** baseline
  (029+030) applied first; confirmed none of the five new tables exist yet; then 031→035 applied
  one at a time, each step independently checked for table existence, column presence, and exactly
  one primary key, with the sentinel fixture re-verified unchanged after EVERY step (not just at
  the end).
- **Existing-data preservation (`test_pg_existing_data_preserved_through_full_chain`):** a sentinel
  task/message/clarification seeded before 031; after the full chain, row count, primary key, and
  every business value are identical (full-row equality, not spot checks); the six new lifecycle
  columns 031 adds to the pre-existing clarification row are confirmed NULL (no inferred backfill).
- **Failure injection, early (`test_pg_failure_early_in_transaction_leaves_no_partial_schema`):** an
  in-memory-only (never file-modified) copy of migration 032 with a failing statement injected
  immediately after `BEGIN` proves NO object from that migration exists after the error.
- **Failure injection, late (`test_pg_failure_just_before_commit_leaves_no_partial_schema`):** the
  same migration with a failing statement injected immediately before `COMMIT` (after all its real
  DDL already ran in the same transaction) proves even a failure at the last possible moment fully
  rolls back — there is no partial commit, and this project has no separate "bookkeeping commit"
  step to fail before (the migration's own `COMMIT` **is** the bookkeeping, since no ledger table
  exists — confirmed in the plan's §2). The unmodified real file was then reapplied and succeeded,
  proving deterministic rerun behavior.
- **Connection/lock release after failure (`test_pg_connection_lock_released_after_failed_migration`):**
  proves an independent, non-obvious PostgreSQL/asyncpg behavior directly (not assumed): a failed
  multi-statement `execute()` leaves the ISSUING connection's session in "aborted transaction" state
  — refusing further commands until an explicit `ROLLBACK` — even though the migration's own data
  changes are already rolled back server-side. A second, independent connection is completely
  unaffected (no global/session lock was left). The failing connection becomes fully usable again
  immediately after a single `ROLLBACK`. **This is documented here as a real operational finding for
  any future migration tooling**: a runner must issue `ROLLBACK` (or reconnect) after a failed
  apply before reusing the same connection — it must not assume the connection is immediately
  reusable. It is not a defect in the migrations themselves.
- **Duplicate invocation (`test_pg_duplicate_migration_invocation_is_idempotent`):** the entire
  chain reapplied a second time in full produces an IDENTICAL schema fingerprint (see below) to the
  first application — confirms the `IF NOT EXISTS` / guarded `ADD CONSTRAINT` idempotency BE1's own
  compatibility record established, now re-verified across the full 031-035 chain together.
- **Out-of-order attempt (`test_pg_out_of_order_migration_attempt_fails_deterministically`):**
  applying 033 (which references `resume_replay_authorizations`) with 032 deliberately skipped fails
  with `UndefinedTableError` and leaves `resume_requests` absent — a clear, deterministic failure,
  not silent corruption.
- **Concurrent migrators (`test_pg_concurrent_migrators_serialize_via_advisory_lock`):** two parts.
  (1) A direct, non-timing-based proof: while one connection holds the migration-chain advisory
  lock, a second connection's `pg_try_advisory_lock` (non-blocking probe) on the SAME key is refused
  immediately, and succeeds only after the first releases — this is option A from the stage's own
  binding requirement, proven directly rather than inferred from wall-clock overlap (an earlier
  draft of this test tried to time whole `apply_chain_locked` calls and produced a false failure,
  because that measurement includes lock-WAIT time, not just lock-HELD time; the direct
  `pg_try_advisory_lock` probe is the correct proof and is what ships here). (2) Two real,
  concurrent `apply_chain_locked` invocations against the same fresh database converge on one
  complete, correct schema (every table present, exactly one primary key each) — no duplicate-DDL
  race, no divergence.
- **Pre-activation down rehearsal (`test_pg_predown_rehearsal_removes_only_new_objects`):** valid
  only because no synthetic BE3 data exists in this fixture — 035→031 down, in reverse order,
  removes exactly the five new tables and nothing else; the pre-031 tables and the sentinel data
  are untouched.
- **Reapply + schema fingerprint (`test_pg_reapply_after_down_matches_original_fingerprint`):** after
  the down rehearsal, 031→035 is reapplied and the resulting schema fingerprint is compared for
  EXACT equality against the fingerprint taken right after the first successful up-rehearsal.
  **Finding and fix**: the first version of `schema_fingerprint` included PostgreSQL's
  auto-generated per-column `NOT NULL` pseudo-constraints (named
  `<namespace_oid>_<table_oid>_<attnum>_not_null` since PG 12) — their names embed the table's OID,
  which changes across a `DROP`+`CREATE`, so comparing them caused a false fingerprint mismatch even
  though the real schema was identical. Fixed by excluding that specific auto-generated-name
  pattern from the constraints query (nullability is already fully captured by
  `information_schema.columns.is_nullable`, so this is not a loss of coverage). After the fix, the
  fingerprints match exactly.
- **Post-write operational rollback simulation (`test_pg_post_write_operational_rollback_is_nondestructive`):**
  synthetic rows inserted into all five new tables; NO destructive down script is run (per the
  binding safety distinction, §4 of the plan); all five rows are confirmed present and unchanged
  afterward; a query using ONLY pre-031 columns against `operator_tasks` still succeeds with the new
  schema present, confirming no old-version compatibility blocker.
- **Guard sanity (`test_pg_no_shared_environment_variables_leaked_into_evidence`):** the fail-closed
  destructive-PG guard (shared with every other Step 66C.4 PostgreSQL test) was never bypassed.

### Regression (real PostgreSQL 16, same isolated container)

```text
tests/ (full step66c4-tagged suite) -> 326 passed / 5 skipped / 3 failed / 4884 deselected
```

The 3 failures are ALL pre-existing on the unmodified baseline commit (18f11fe), confirmed by
re-running them against a clean checkout of that commit before any RA-1A file was overlaid:

```text
test_step66c4_be1_merge.py::test_no_live_outbox_producer_on_main -- a Step 66C.4-BE1-M historical
  verifier that predates BE3's (already-merged, PO-authorized) replay/resume modules referencing
  the outbox; same expected/benign pattern already documented for BE3-C's own historical verifier
  vs. migration 035. Not modified, per the standing rule never to weaken/modify a prior stage's
  verifier.
test_step66c4_be3_planning.py::test_no_backend_api_migration_frontend_deployment_code_changed -- a
  Step 66C.4-BE3-P planning-stage historical test comparing against a pre-implementation baseline
  ref; BE3-A/B/C's own (already-merged, PO-authorized) implementation has since legitimately
  changed apps/shared/migrations. Not modified.
test_step66c4_be3_runtime_activation_planning.py::test_verifier_script_passes -- this remote host's
  PATH has no bare "python" (only "python3" and the venv's absolute interpreter path); a
  pre-existing environment-specific quirk, confirmed present before any RA-1A change and unrelated
  to migration rehearsal. Out of this stage's scope to fix (RA-1A's allowed changes are scoped to
  migration-rehearsal artifacts only).
```

No failure introduced by RA-1A's own files.

## Quality gates

```text
ruff check (changed Python files):    PASS
black --check (changed Python files): PASS
mypy (changed modules):               PASS
git diff --check:                     PASS
Secret / internal-identifier scan of committed files: PASS
scripts/verify_step66c4_be3_ra1_migration_rehearsal.py: PASS
```

## Posture

```text
Migrations 031-035: UNCHANGED, no defect found requiring remediation.
Gates 1/2/6 (be3-runtime-activation-gate.md): IMPLEMENTED / REHEARSED, PENDING RA-1R independent
  review -- NOT marked CLOSED by this self-verified stage.
New migration-runner safeguard (shared/sdk/backup_dr/migration_runner.py): additive, closes the
  previously-open concurrent-migrator gap via a session-level advisory lock; does not modify any
  existing migration file.
Shared/test/staging/production database: untouched.
All four BE3 feature gates: confirmed false throughout (re-checked after the rehearsal).
Worker/relay/consumer: none started.
production_executed_true_count: 0.
Next: independent review (Step 66C.4-BE3-RA-1R) is the required next gate before Gates 1/2/6 may be
  marked CLOSED or before any further RA-stage begins.
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
