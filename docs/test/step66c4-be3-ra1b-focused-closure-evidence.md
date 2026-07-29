# Step 66C.4-BE3-RA-1FC — Focused Closure Test & Evidence Record

> **Independent focused-closure evidence by the original RA-1R reviewer. All PostgreSQL work ran on
> an isolated ephemeral PostgreSQL 16.14 container on an internal test runtime (distinct container
> name and port from every prior RA-1 stage), destroyed after the review. No shared database was
> touched. NOT FOR MERGE / NOT deployed / NOT activated.**

## Markers

```text
STEP66C4_BE3_RA1B_FOCUSED_CLOSURE_VERIFY: PASS      (process/artifacts complete)
RA1_TECHNICAL_VERDICT: REMEDIATION_REQUIRED          (H-1 CLOSED, M-1 CLOSED, M-2 + M-3 not closed)
```

## Environment

```text
Runtime:      internal test runtime; isolated ephemeral PostgreSQL 16.14 container on a dedicated
              port distinct from every prior RA-1 rehearsal/review/remediation container, created
              for this closure and destroyed afterward. Isolated DB name matches the fail-closed
              guard's ephemeral_*/*_test convention (never committed).
Guard opt-in: STEP66C4_ALLOW_DESTRUCTIVE_PG_TESTS=1 with an isolated DSN (never committed).
Worktrees:    two detached worktrees on the internal test runtime — one at the reviewed remediation
              head b31e655, one at the reviewed baseline 18f11fe — plus a reviewer-only integration
              merge (19cff82) on the review branch bringing b31e655 into the tree for in-place
              inspection. All removed after the review.
Reviewer:     the ORIGINAL RA-1R reviewer (continuity); did NOT participate in RA-1B implementation.
              Conclusions re-derived from committed source + direct experiments, not RA-1B's records.
```

## Independent focused-closure test suite

`tests/test_step66c4_be3_ra1b_focused_closure.py` — **20 passed, 0 skipped, 0 failed** on real
PostgreSQL 16. A faithful characterization: it asserts the ACTUAL observed behavior, including the
two M-2 gaps and the M-3 redaction gap, so it passes against the code under review while the review
document interprets it.

```text
H-1  test_h1_rollback_before_unlock_preserves_original_error_and_reuses_connection  PASS
     test_h1_forced_backend_termination_disposes_connection                          PASS
     test_h1_cancellation_while_holding_lock_releases_and_propagates                  PASS
     test_h1_pool_returns_clean_connection_after_failed_migration                     PASS
     test_h1_cleanup_error_attribute_attaches_to_realistic_exception_types            PASS
M-1  test_m1_all_semantic_mutations_detected  (11 categories + determinism + round-trip)  PASS
M-2  test_m2_ledger_apply_checksum_untracked_and_reconcile                            PASS
     test_m2_untracked_schema_and_partial_applying_fail_closed                        PASS
     test_m2_ambiguous_commit_reconciles_when_schema_present                          PASS
     test_m2_GAP_reconcile_accepts_wrong_shaped_table          (characterizes gap B)  PASS
     test_m2_GAP_down_then_reapply_lifecycle_is_inconsistent   (characterizes gap A)  PASS
     test_m2_wrong_shaped_ledger_table_fails_closed                                   PASS
     test_m2_baseline_029_030_boundary                                                PASS
M-3  test_m3_bounded_lock_wait_timeout_and_release                                    PASS
     test_m3_invalid_timeout_config_fails_closed                                      PASS
     test_m3_statement_timeouts_set_and_restored                                      PASS
     test_m3_plan_mode_no_writes_across_schema_states  (5 states)                     PASS
     test_m3_cli_exit_codes_and_json_output  (0/1/2, single JSON)                     PASS
     test_m3_GAP_redactor_misses_postgresql_scheme             (characterizes gap)    PASS
§19  test_s19_allowlist_additions_are_precise_no_broadening                          PASS
```

## Re-derivation of RA-1B's own suite + directly-affected RA-1 suites

```text
tests/test_step66c4_be3_ra1_migration_rehearsal.py (RA-1A)      -> 12 passed
tests/test_step66c4_be3_ra1b_migration_runner_remediation.py    -> 23 passed
tests/test_step66c4_be3_ra1b_focused_closure.py (this closure)  -> 20 passed
                                                          total  -> 55 passed / 0 failed / 0 skipped
```

## Key empirical results (raw)

H-1 (failure/cancellation/pool):

```text
mid-file failure: propagated=DivisionByZeroError (ORIGINAL, not masked); ra1b_cleanup_errors=[];
                  ra1b_connection_reusable=True; connection reusable (SELECT 1 ok); lock released.
forced backend kill mid-migration: ra1b_connection_reusable=False; conn.is_closed()=True (disposed).
cancellation while holding lock: CancelledError propagates; lock released after.
asyncpg.Pool(max_size=1): next borrower after a failed migration is clean, no lock leak.
attribute attach on ZeroDivisionError/CancelledError/PostgresError/MigrationLockTimeoutError/
                     SchemaDriftError/TimeoutError/KeyboardInterrupt -> all accept it (no masking).
```

M-1 (all §8 mutations detected = True):

```text
check_expr_samename, fk_on_delete, fk_on_update, fk_MATCH_full, fk_deferrability,
validation_state (NOT VALID->valid), partial_predicate, index_expression,
index_access_method_samename, column_default, nullability (+ round-trip fingerprint-equal)
```

M-2 (gaps, raw):

```text
after ledger apply 031-035 then raw down 035->031:
  tables_exist_after_down  = {all five: False}
  ledger_after_down        = {031..035: 'applied'}       <- stale, still claims applied
  plan.drift_status        = {031..035: 'ok'}            <- does NOT fail closed
  plan.schema_state        = {031..035: False}
  plan.pending_versions    = []    plan.current_version = '035'
  reapply result_code      = 'success'  applied=[]  reconciled=[]   tables still absent
reconcile of wrong-shaped table (applying row + real checksum + table ALTERED):
  outcome = RECONCILED (reconciled_versions=['032'])     <- wrong shape accepted
wrong-shaped ledger table -> FAILED_CLOSED (UndefinedColumnError)
```

M-3 (redaction, raw):

```text
redact("postgresql://user:hunter2pw@examplehost:5432/db") = "postgresql://user:hunter2pw@examplehost:5432/db"  (UNREDACTED)
redact("postgres://user:hunter2pw@h/db")               = "[redacted: message contained secret-shaped content]"
redact("password authentication failed")               = "[redacted: message contained secret-shaped content]"
CLI --apply with a wrong-password DSN: prints a raw Python traceback to stderr, exit 1
  (asyncpg InvalidPasswordError message does NOT contain the password value -> no credential-VALUE
   leak demonstrated, but the output is an unredacted traceback, not the §18 single-JSON object).
```

## Regression (independently re-run on both commits)

```text
baseline 18f11fe (step66c4-tagged):  3 failed / 314 passed / 5 skipped
feature  b31e655 (step66c4-tagged):  3 failed / 369 passed / 5 skipped   (314 + 12 + 23 + 20)
```

Same three pre-existing failures (identical node IDs) on both; none migration/backup/CLI-related;
no new feature-only failure; no additional skip; no assertion weakened; both BE1 allowlist guards
PASS on feature.

## Quality gates (this closure's two added Python files)

```text
ruff check:            PASS
black --check:         PASS
mypy:                  PASS (no issues)
git diff --check:      PASS
secret / internal-identifier scan of committed closure files: PASS (neutral labels only)
scripts/verify_step66c4_be3_ra1b_focused_closure.py: PASS (process marker)
```

## Safety boundary

```text
Shared database applied:            NONE
Deployment:                         NONE
Feature gates enabled:              NONE (all four BE3 gates remain default-false)
Worker/relay/consumer started:      NONE
Runtime resume/replay executed:     NONE
Files under review modified:        NONE (migration_runner.py, run_platform_migrations.py,
                                    migrations/*, RA-1A + RA-1B suites, both BE1 guards — unchanged)
PR #21:                             Draft/OPEN/unmerged before and after (unchanged)
production_executed_true_count: 0
```

---
_Non-production only. No production action. No production data. Neutral labels only — no internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets ("internal test runtime", "isolated ephemeral PostgreSQL 16")._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
