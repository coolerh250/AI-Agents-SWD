# Step 66C.4-BE3-RA-1FC2 — Second Focused Closure Test & Evidence Record

> **Independent second focused-closure evidence by the original RA-1R / RA-1FC reviewer. All
> PostgreSQL work ran on a fresh isolated ephemeral PostgreSQL 16.14 container on an internal test
> runtime (distinct container name and port from every prior RA-1 stage), destroyed after the
> review. No shared database was touched. NOT FOR MERGE / NOT deployed / NOT activated.**

## Markers

```text
STEP66C4_BE3_RA1C_SECOND_FOCUSED_CLOSURE_VERIFY: PASS      (process/artifacts complete)
RA1_TECHNICAL_VERDICT: REMEDIATION_REQUIRED                (M-2A/M-2B/M-3A CLOSED; M-3B narrow residual)
```

## Environment

```text
Runtime:      internal test runtime; fresh isolated ephemeral PostgreSQL 16.14 container on a
              dedicated port distinct from every prior RA-1 stage; created for this closure and
              destroyed afterward. Isolated DB name matches the fail-closed guard's ephemeral_*/*_test
              convention (never committed).
Guard opt-in: STEP66C4_ALLOW_DESTRUCTIVE_PG_TESTS=1 with an isolated DSN (never committed).
Worktrees:    detached worktrees on the internal test runtime at the reviewed remediation head
              7820b4b and the reviewed baseline 18f11fe, plus a reviewer-only integration merge
              (07f839f) on the review branch bringing 7820b4b into the tree for in-place inspection.
              All removed after the review.
Reviewer:     the ORIGINAL RA-1R / RA-1FC reviewer (continuity); did NOT participate in RA-1C
              implementation. Conclusions re-derived from committed source + direct experiments.
```

## Independent second focused-closure suite

`tests/test_step66c4_be3_ra1c_second_focused_closure.py` — **16 passed, 0 skipped, 0 failed** on real
PostgreSQL 16. A faithful characterization: it asserts the ACTUAL observed behavior, including the
M-3B missing-config residual, so it passes against the code under review while the review document
interprets it.

```text
M-2A test_m2a_fresh_apply_marks_all_applied_and_reverifies_clean                          PASS
     test_m2a_applied_but_schema_mutated_fails_closed  (7 mutation cases)                 PASS
     test_m2a_reconciled_row_later_drift_fails_closed                                     PASS
     test_m2a_raw_down_then_plan_and_apply_fail_closed_then_fresh_db_reapply              PASS
M-2B test_m2b_manifest_inventory_complete_and_owned_object_scoped                         PASS
     test_m2b_no_runtime_manifest_generation_path                                         PASS
     test_m2b_manifest_fail_closed_cases                                                  PASS
     test_m2b_expected_fingerprint_recorded_before_ddl                                    PASS
     test_m2b_ambiguous_reconcile_strict_matrix  (6 accept/reject cases)                  PASS
M-3A test_m3a_all_schemes_and_kv_and_userinfo_redacted                                    PASS
     test_m3a_diagnostic_codes_survive_redaction                                          PASS
M-3B test_m3b_success_plan_and_apply_single_json_stdout                                   PASS
     test_m3b_connect_failures_single_json_no_secret  (malformed/unreachable/auth x plan/apply)  PASS
     test_m3b_missing_config_exit_2   (characterizes the plain-text residual)             PASS
     test_m3b_debug_logging_does_not_pollute_connect_failure                              PASS
§20  test_s20_adjusted_ra1b_tests_not_weakened                                            PASS
```

## Directly-affected RA-1 suites (independent re-derivation)

```text
tests/test_step66c4_be3_ra1_migration_rehearsal.py (RA-1A)      -> 12 passed
tests/test_step66c4_be3_ra1b_migration_runner_remediation.py    -> 23 passed
tests/test_step66c4_be3_ra1c_ledger_schema_cli.py (RA-1C)       -> 31 passed
tests/test_step66c4_be3_ra1c_second_focused_closure.py (this)   -> 16 passed
                                                          total  -> 82 passed / 0 failed / 0 skipped
```

## Key empirical results (raw)

M-2A (ledger vs actual schema):

```text
fresh apply 031-035: result_code=success, applied=[031..035]; second run applied=[]/reconciled=[]
                     (re-verified + skipped); plan.result_code=success, current_version=035.
applied + {DROP TABLE | DROP COLUMN | DROP INDEX | changed CHECK | changed FK ON DELETE |
           changed FK ON UPDATE | extra column}:
           plan.result_code != success, drift_status contains ledger_schema_mismatch;
           apply raises LedgerSchemaMismatchError; dropped object NOT recreated.
reconciled row + later DROP COLUMN: plan drift_status[032]=ledger_schema_mismatch; apply raises.
raw down 035-031 after clean apply:
           tables all absent; plan.result_code="ledger_schema_mismatch"; current_version != 035;
           apply raises LedgerSchemaMismatchError; tables NOT recreated; ledger rows still 'applied'
           (never auto-edited). destroy+recreate DB -> baseline -> apply -> applied=[031..035].
```

M-2B (manifest + expected fingerprint):

```text
5 manifests: all 7 fields present + correct; owned_objects scoped (031 owns outbox+ocr; 032-035 own
             only their created table). No runtime regeneration path (source-verified).
fail-closed: missing manifest / checksum mismatch -> MigrationManifestError.
pre-DDL:     inject failure at DDL time -> ledger row already has expected_fingerprint == manifest
             fingerprint + filename + checksum (recorded before any DDL).
reconcile:   correct->reconciled; null expected->ExpectedFingerprintMissingError; wrong-shape /
             missing-index / changed-CHECK / tampered-expected -> SchemaDriftError.
```

M-3A (redaction):

```text
postgres:// postgresql:// postgresql+asyncpg:// redis:// rediss:// http:// https://  -> all collapsed;
  none of {password, host, username, port, database} survive.
?password= ?secret= ?token= ?apikey= ?api_key= password= "token:" dsn= bare user:pass@host -> collapsed.
diagnostic codes (database_connect_failed / migration_checksum_mismatch / ledger_schema_mismatch /
  untracked_schema / expected_fingerprint_missing) -> returned verbatim (not clobbered).
```

M-3B (CLI):

```text
success --plan/--apply: exit 0; stdout = one JSON object; stderr empty.
connect failure (malformed / unreachable / auth) x (--plan/--apply): exit 1; stdout empty; stderr =
  one JSON object {result_code: database_connect_failed}; no traceback; no secret/host/port/db.
  (holds under PYTHONASYNCIODEBUG=1.)
missing configuration (DSN unset): exit 2; no traceback; no secret -- BUT stderr is a PLAIN-TEXT line,
  NOT the single JSON object spec section 17 requires (does not parse as JSON). [M-3B residual]
```

## Regression (independently re-run on both commits)

```text
baseline 18f11fe (step66c4-tagged):  3 failed / 314 passed / 5 skipped
feature  7820b4b (step66c4-tagged):  3 failed / 396 passed / 5 skipped   (314 + 12 + 23 + 31 + 16)
```

Same three pre-existing failures (identical node IDs) on both; none migration/backup/CLI-related; no
new feature-only failure; no additional skip; no assertion weakened; both BE1 allowlist guards PASS
on feature.

## Quality gates (this closure's two added Python files)

```text
ruff check:            PASS
black --check:         PASS
mypy:                  PASS (no issues)
git diff --check:      PASS
secret / internal-identifier scan of committed closure files: PASS (neutral labels only; the redaction
  test fixtures use fabricated dummies -- ra1user / internal-db.example / a placeholder password -- not
  any real internal identifier)
scripts/verify_step66c4_be3_ra1c_second_focused_closure.py: PASS (process marker)
```

## Safety boundary

```text
Shared database applied:            NONE
Deployment:                         NONE
Feature gates enabled:              NONE (all four BE3 gates remain default-false)
Worker/relay/consumer started:      NONE
Runtime resume/replay executed:     NONE
Files under review modified:        NONE (migration_runner.py, run_platform_migrations.py, the five
                                    manifests, migrations/*, and the RA-1A/RA-1B/RA-1C suites are
                                    byte-identical to 7820b4b)
PR #21:                             Draft/OPEN/unmerged before and after (unchanged)
production_executed_true_count: 0
```

---
_Non-production only. No production action. No production data. Neutral labels only — no internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets ("internal test runtime", "isolated ephemeral PostgreSQL 16")._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
