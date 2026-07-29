# Step 66C.4-BE3-RA-1B — Migration Runner Safety, Provenance and Operational Controls Remediation

> **Remediation record. Closes H-1, M-1, M-2, M-3 from the Step 66C.4-BE3-RA-1R independent review.
> Performed by the original RA-1A implementation session, per this stage's own instruction. NOT
> applied to any shared database. NOT deployed. NOT activated. Draft PR #21 remains Draft/OPEN/NOT
> FOR MERGE. Migrations 029-035 are UNCHANGED.**

## 1. Review evidence preserved first

Before any implementation change, `origin/review/66c4-be3-ra1-migration-rollback` was confirmed
pushed at commit `352d546` (append-only; no PR opened, no merge performed), per this stage's own
§2 requirement.

## 2. H-1 — aborted-transaction cleanup / lock-release failure

**Finding:** `apply_chain_locked`'s `finally` block attempted `pg_advisory_unlock` directly on a
connection already left in an aborted-transaction state by a failed migration; that unlock attempt
itself failed (`InFailedSQLTransactionError`), masking the real migration error, and the lock was
never released via `unlock` at all (only eventually via connection teardown).

**Fix.** The required cleanup order is now:

```text
capture original exception -> explicit ROLLBACK -> advisory unlock -> (M-3: restore session
timeouts) -> re-raise the ORIGINAL exception
```

- `ROLLBACK` is attempted BEFORE `unlock`, on every failure path.
- Every cleanup step (`ROLLBACK`, `unlock`, timeout restore) is independently wrapped in
  `_safe_cleanup_step`, which never raises -- it returns the exception (if any) instead, so a
  cleanup failure can never replace or hide the original migration error.
- Every cleanup step is bounded (`asyncio.wait_for` + `asyncio.shield`, `CLEANUP_STEP_TIMEOUT_SECONDS
  = 10s`), so cleanup can never hang forever, and is cancellation-safe (a `CancelledError` at the
  call site does not abandon a cleanup step mid-flight).
- `BaseException` (not just `Exception`) is caught at every relevant boundary, so `CancelledError`
  is captured, cleaned up, and (as `asyncio` requires) still ultimately propagates.
- If ANY cleanup step fails, the connection is proactively closed (`await conn.close()`,
  best-effort) rather than handed back to the caller in an unknown state, and
  `original_error.ra1b_connection_reusable` is set to `False` (`True` when cleanup was clean) so a
  caller can also programmatically check.
- The ORIGINAL exception is always what propagates; `.ra1b_cleanup_errors` carries any cleanup
  failures as attached, non-masking metadata.

## 3. M-1 — schema fingerprint semantic completeness

**Finding:** the constraints query only exposed `constraint_name`/`constraint_type` -- CHECK
expression bodies, FK ON DELETE/ON UPDATE/MATCH actions, and deferrability were invisible to the
fingerprint, so those categories of drift could go undetected.

**Fix.** `_CONSTRAINTS_QUERY` now reads directly from `pg_constraint` (joined to `pg_class`/
`pg_namespace`), returning `pg_get_constraintdef(con.oid)` -- PostgreSQL's own canonical semantic
definition string, which includes CHECK expression bodies, FK source/target columns, FK ON DELETE/
ON UPDATE/MATCH actions, and any non-default deferrability clause -- plus explicit
`deferrable`/`initially_deferred`/`validated` boolean columns. `_INDEXES_QUERY` (unchanged logic,
already using `pg_indexes.indexdef`, which itself already captures partial-index predicates and
index expressions) gains an explicit `access_method` column. The OID-embedded auto-generated NOT
NULL exclusion is preserved (harmlessly redundant now that PG 16's `pg_constraint` does not
represent plain-column NOT NULL at all -- nullability is captured by
`information_schema.columns.is_nullable`, confirmed independently during remediation testing).

## 4. M-2 — migration ledger and version provenance

**Finding:** no ledger/bookkeeping table existed anywhere; "applied" was determined purely by schema
introspection, with no version/checksum provenance, no drift detection beyond bare object existence,
and no distinction between "this schema was created by this runner" and "this schema exists for
some unknown reason."

**Fix.** A new, additive, runner-owned table `platform_schema_migrations` (bootstrapped via
`ensure_ledger_bootstrapped`, called AFTER the migration-chain advisory lock is held, so two
concurrent callers never race to create it) records, per apply attempt: `migration_version`,
`migration_filename`, `migration_sha256`, `status`, `runner_version`, timestamps, and
`expected_fingerprint`/`observed_fingerprint`. `apply_chain_with_ledger` uses it as follows:

```text
status='applied', checksum matches file on disk       -> skip (ledger-authoritative idempotency)
status='applied', checksum DIFFERS from file on disk  -> MigrationChecksumMismatchError, fail closed
                                                          (row never overwritten, never re-run)
status='applying' (ambiguous prior attempt), filename/checksum match AND target schema complete AND
  observed fingerprint matches the recorded expected fingerprint
                                                       -> reconciled_after_ambiguous_commit
status='applying', filename/checksum mismatch, OR schema incomplete, OR fingerprint mismatch
                                                       -> SchemaDriftError, status='drifted', chain
                                                          stops, operator action required
no ledger row, target table(s) already exist          -> UntrackedSchemaError ("UNTRACKED_SCHEMA"),
                                                          NEVER auto-adopted
no ledger row, no existing schema                     -> normal apply: insert 'applying' row ->
                                                          run the migration file -> record the
                                                          observed fingerprint -> mark 'applied'
```

The migration file's own `BEGIN/COMMIT` and the ledger's own row updates are explicitly DIFFERENT
transactions (the ledger's applying-row INSERT is a separate, auto-committed statement executed
BEFORE the migration file runs; the applied/failed/drifted UPDATE runs AFTER, once the connection
is confirmed usable again post-ROLLBACK-if-needed) -- this is stated here and in the module's own
docstring, per this stage's explicit requirement never to conflate the two.

## 5. M-3 — bounded waits and operational controls

**Finding:** `pg_advisory_lock` blocks indefinitely; no statement/lock timeout was ever set; no
dry-run/plan capability existed; nothing gave an operator a clear exit code or structured result.

**Fix.**

- The advisory lock wait is now bounded: `_acquire_lock_bounded` polls `pg_try_advisory_lock`
  against a monotonic deadline (`lock_wait_timeout_seconds`, default 30s, bounds [1s, 300s];
  `poll_interval_seconds`, default 0.2s, bounds [0.05s, 5s]). A timeout raises
  `MigrationLockTimeoutError` cleanly -- no transaction or session lock is left behind, since no
  lock was ever acquired.
- `statement_timeout`/`lock_timeout`/`idle_in_transaction_session_timeout` are set (bounded,
  [1000ms, 600000ms], default 30000ms) before applying and restored to their PRIOR values
  afterward; if the restore itself fails, the connection is discarded (folded into the same
  cleanup-error/connection-disposal logic as H-1).
- Invalid configuration (out-of-bounds timeout, `poll_interval_seconds` exceeding
  `lock_wait_timeout_seconds`) raises `MigrationConfigError` immediately -- fails closed, never
  silently clamped.
- `plan_chain` is a read-only inspection (no DDL, no ledger writes, no lock held) reporting current/
  target version, pending migrations, checksums, per-version drift status, untracked-schema
  status, and expected operations.
- `scripts/run_platform_migrations.py --plan` / `--apply` is the operator-facing entry point:
  `PLATFORM_MIGRATIONS_DATABASE_URL` from the environment only (never hardcoded, never logged);
  exit 0 only on unambiguous success; exit 1 on any drift/checksum/migration failure; exit 2 if the
  DSN is missing; every error passed through `redact_for_operator` (never prints a DSN, password,
  token, or credential-shaped string); output is a single structured JSON object.

## 6. Scope discipline

```text
Modified:   shared/sdk/backup_dr/migration_runner.py (allowed change)
Added:      scripts/run_platform_migrations.py, tests/test_step66c4_be3_ra1b_migration_runner_
            remediation.py, this record, the evidence record, the handoff record, the self-verifier
Also fixed: two PRE-EXISTING BE1/BE1-R1 static-guard test allowlists (test_step66c4_be1_data_model_
            deadline_outbox.py, test_step66c4_be1_r1_remediation.py) -- both already explicitly
            document an established, repeatedly-exercised amendment pattern ("Updated in BE2, then
            BE3-B, then BE3-C") for legitimately-authorized new files that merely NAME the outbox
            table as a string without importing or driving it; migration_runner.py's fingerprint
            catalog needed the real table name and triggered the same substring guard, so it was
            added to both allowlists following the identical, already-established pattern -- this
            is "direct tests/verifiers" maintenance explicitly allowed by this stage's own scope,
            not a weakening of either guard's actual security property (no live producer/consumer).
NOT touched: migrations/029-035 (unchanged; no defect was found in them), any BE3 runtime service,
            any feature-gate default, any deployment configuration, any Compose/Helm/Kubernetes
            runtime value, any file on the review branch (352d546).
```

## Statement

Remediation record only. No shared migration application. No deployment. No feature-gate change.
No runtime validation. No production or external action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
