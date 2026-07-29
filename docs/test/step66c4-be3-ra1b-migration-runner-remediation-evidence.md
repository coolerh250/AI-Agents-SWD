# Step 66C.4-BE3-RA-1B — Migration Runner Remediation Test & Validation Record

> **Test record. Closes H-1, M-1, M-2, M-3 from the Step 66C.4-BE3-RA-1R independent review. NOT
> applied to any shared, test, staging, or production database. All PostgreSQL work ran on an
> isolated ephemeral container, destroyed afterward. NOT FOR MERGE.**

## Marker

```text
STEP66C4_BE3_RA1B_MIGRATION_RUNNER_REMEDIATION_VERIFY: PASS
```

## Environment

```text
Runtime:      internal test runtime (isolated ephemeral PostgreSQL 16 container on a dedicated
              port distinct from every prior RA-1 rehearsal/review container), created for this
              run and destroyed afterward. Isolated DB name step66c4_ra1b_migration_remediation
              (fail-closed guard; not shared).
Guard opt-in: STEP66C4_ALLOW_DESTRUCTIVE_PG_TESTS=1 with an isolated DSN (never committed).
Worktree:     detached at the reviewed feature head (27184b5) with the uncommitted RA-1B files
              overlaid; removed after the run. The shared aiagents-test stack's postgres/redis
              containers were already in an "Exited" state (host-level restart, unrelated to this
              session) before this stage began and remained so throughout -- confirmed untouched.
```

## Results

### New: RA-1B migration runner remediation (real PostgreSQL 16)

```text
tests/test_step66c4_be3_ra1b_migration_runner_remediation.py -> 23 passed / 0 skipped / 0 failed
```

Coverage, matching every §22-mandated scenario:

**H-1:**
- `test_pg_mid_file_failure_rolls_back_before_unlock_and_preserves_original_error`: a genuine
  in-transaction PostgreSQL error propagates as itself (`DivisionByZeroError`), with
  `.ra1b_connection_reusable is True` and `.ra1b_cleanup_errors == []`; the connection is
  immediately reusable (`SELECT 1` succeeds) -- proves ROLLBACK ran before unlock.
- `test_pg_failure_just_before_commit_rollback_and_lock_released`: a late (pre-COMMIT) failure
  still rolls back fully and releases the lock (a second connection acquires it immediately via
  `pg_try_advisory_lock`).
- `test_pg_cancellation_while_lock_held_releases_lock`: a task holding the lock, cancelled mid-
  migration (via `asyncio.Task.cancel()`), still releases the lock -- confirmed by a second
  connection's immediate `pg_try_advisory_lock` success.
- `test_pg_rollback_failure_causes_connection_disposal`: the connection's OWN backend is forcibly
  terminated (`pg_terminate_backend`, from an admin connection) mid-migration, so the runner's own
  internal ROLLBACK attempt itself fails; `.ra1b_connection_reusable is False` and the connection
  is confirmed closed by the runner.
- `test_pg_fresh_connection_after_disposal_is_unaffected`: a brand-new connection after a disposal
  is completely unaffected -- no lingering session- or database-level poisoning.

**M-1:**
- `test_pg_fingerprint_detects_check_expression_change`, `..._fk_on_delete_change`,
  `..._fk_on_update_change`, `..._deferrability_change`,
  `..._index_predicate_and_expression_change`: each of the five targeted mutations changes the
  fingerprint, proving `pg_get_constraintdef` and `pg_indexes.indexdef` capture CHECK expressions,
  FK ON DELETE/ON UPDATE actions, deferrability, and index predicates/expressions respectively.
- `test_pg_fingerprint_still_detects_drop_index_nullability_and_default`: index drop, a genuine
  nullability toggle (on `requested_by`, which IS `NOT NULL` in the real schema -- an earlier draft
  of this test mistakenly toggled the already-nullable `decided_by` and was corrected after the
  real ephemeral-PostgreSQL run caught the logic error), and a default-expression change are all
  still detected; a true round-trip (drop NOT NULL, then restore it) returns to the exact original
  fingerprint.

**M-2:**
- `test_pg_ledger_bootstrap_and_applied_status_checksum`: the ledger bootstraps additively; all
  five migrations end in `status='applied'` with the correct SHA-256 recorded.
- `test_pg_duplicate_invocation_uses_ledger_fast_path`: a second full-chain call applies nothing
  new (ledger-authoritative skip), not a blind re-execution.
- `test_pg_checksum_mismatch_fails_closed`: a ledger row's checksum is corrupted by hand;
  `MigrationChecksumMismatchError` is raised and the corrupted row is NEVER silently overwritten.
- `test_pg_ambiguous_commit_reconciles_when_schema_matches`: the classic "server committed, client
  never got the ack" scenario is simulated (the migration's real DDL is applied out-of-band, then a
  matching `applying` ledger row is inserted by hand); a retry reconciles
  (`status='reconciled_after_ambiguous_commit'`) rather than re-executing or failing.
- `test_pg_untracked_schema_rejected`: a FOREIGN, wrong-shaped object under the migration's own
  target table name, with NO ledger row, is never silently adopted --
  `UntrackedSchemaError`/`UNTRACKED_SCHEMA` is raised and the foreign object is untouched.
- `test_pg_partial_schema_in_applying_state_rejected_as_drifted`: an `applying` ledger row with NO
  matching schema object at all is rejected as drifted, not treated as reconcilable.
- `test_pg_failed_migration_ledger_state_recorded`: a genuinely failing migration file records
  `status='failed'` with a non-null, secret-free `error_code`.

**M-3:**
- `test_pg_lock_wait_timeout_raises_and_does_not_hang`: a held lock causes a bounded
  `MigrationLockTimeoutError` within the configured window, not an indefinite hang.
- `test_pg_statement_timeout_applied_and_restored`: `statement_timeout` (and its siblings) is
  restored to its exact prior value after a successful run.
- `test_pg_invalid_timeout_config_fails_closed`: out-of-bounds lock-wait, poll-interval, and
  statement-timeout values all raise `MigrationConfigError` immediately.
- `test_pg_plan_mode_produces_no_writes`: `plan_chain` creates neither the ledger table nor any of
  the five migration tables.
- `test_cli_plan_and_apply_exit_codes_and_secret_redaction`: the CLI's `--plan` and `--apply` exit
  0 on success with a DSN-free structured JSON payload on stdout; a second `--apply` is idempotent
  (0 new applied versions); a missing DSN exits 2.

### Regression (real PostgreSQL 16, same isolated container)

```text
tests/test_step66c4_be3_ra1_migration_rehearsal.py + tests/test_step66c4_be3_ra1b_migration_runner_
remediation.py -> 35 passed / 0 skipped / 0 failed (12 + 23; no RA-1A test needed modification --
none of its existing assertions exercise apply_chain_locked's failure path or rely on
schema_fingerprint's exact literal content, only fingerprint EQUALITY, which the enriched output
still satisfies).

Full step66c4-tagged suite -> 349 passed / 5 skipped / 3 failed / 4884 deselected.
```

The 3 failures are the SAME three the RA-1A stage already identified as pre-existing on the
unmodified baseline (confirmed unchanged in signature and root cause):

```text
test_step66c4_be1_merge.py::test_no_live_outbox_producer_on_main -- stale BE1-M historical verifier
  predating BE3's already-merged replay/resume modules.
test_step66c4_be3_planning.py::test_no_backend_api_migration_frontend_deployment_code_changed --
  stale BE3-P planning-stage git-diff guard vs. an old baseline ref.
test_step66c4_be3_runtime_activation_planning.py::test_verifier_script_passes -- this remote host's
  PATH has no bare "python" (pre-existing environment quirk, confirmed present before RA-1A too).
```

Two OTHER guard tests initially showed a NEW failure during this stage
(`test_step66c4_be1_data_model_deadline_outbox.py::test_outbox_module_has_no_live_producer_import`
and `test_step66c4_be1_r1_remediation.py::test_no_relay_scheduler_or_live_producer_exists`) because
`migration_runner.py`'s fingerprint catalog names the real table `clarification_lifecycle_outbox`
as a plain string (needed to query the actual database table -- not an import of, or a producer/
consumer relationship with, `lifecycle_outbox.py`). Both guards already document and have
repeatedly exercised the exact same amendment pattern for legitimately-authorized additions ("no
producer/consumer, just a string reference") across BE2, BE3-B, and BE3-C; `migration_runner.py` was
added to both allowlists following that identical, already-established pattern. Confirmed AFTER the
fix: full step66c4 suite returns to exactly the same 3 pre-existing failures, with 2 more tests now
passing (347 -> 349) than the RA-1A baseline run, and no assertion in either guard was weakened --
both still reject any OTHER unlisted file that references the outbox.

## Quality gates

```text
ruff check (changed Python files):    PASS
black --check (changed Python files): PASS
mypy (changed modules):               PASS
git diff --check:                     PASS
Secret / internal-identifier scan of committed files: PASS
scripts/verify_step66c4_be3_ra1b_migration_runner_remediation.py: PASS
```

## Posture

```text
H-1: CLOSED -- explicit ROLLBACK before unlock; original error never masked; every cleanup step
     bounded and cancellation-safe; connection disposed on any cleanup failure.
M-1: CLOSED -- CHECK expressions, FK ON DELETE/ON UPDATE/MATCH actions, deferrability, index
     predicates/expressions all independently proven detected.
M-2: CLOSED -- additive runner-owned ledger; checksum-mismatch and untracked-schema both fail
     closed; ambiguous-commit reconciliation only under strict, independently-tested conditions.
M-3: CLOSED -- bounded lock-wait and statement timeouts; invalid config fails closed; read-only
     plan mode; operator CLI with clear exit codes and secret-free structured output.
Migrations 031-035: UNCHANGED. Review branch 352d546: UNCHANGED, unmerged.
Shared/test/staging/production database: untouched. All four BE3 feature gates: unaffected by this
  stage (unchanged, still default-false). Worker/relay/consumer: none started.
production_executed_true_count: 0.
Next: independent RA-1R's own reviewer -- the original RA-1R reviewer, not this session -- performs
  a focused closure over H-1/M-1/M-2/M-3 before Gates 1/2/6 may be marked CLOSED. Draft PR #21
  remains Draft/OPEN/NOT FOR MERGE.
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
