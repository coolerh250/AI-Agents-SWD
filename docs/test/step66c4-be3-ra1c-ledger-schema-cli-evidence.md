# Step 66C.4-BE3-RA-1C — Ledger/Schema Consistency and CLI Redaction Test & Validation Record

> **Test record. Closes M-2A, M-2B, M-3A, M-3B from the Step 66C.4-BE3-RA-1FC focused closure. NOT
> applied to any shared, test, staging, or production database. All PostgreSQL work ran on an
> isolated ephemeral container, destroyed afterward. NOT FOR MERGE.**

## Marker

```text
STEP66C4_BE3_RA1C_LEDGER_SCHEMA_CLI_VERIFY: PASS
```

## Environment

```text
Runtime:      internal test runtime (isolated ephemeral PostgreSQL 16 container on a dedicated
              port distinct from every prior RA-1 rehearsal/review container), created for this
              run and destroyed afterward. Isolated DB name step66c4_ra1c (fail-closed guard; not
              shared).
Guard opt-in: STEP66C4_ALLOW_DESTRUCTIVE_PG_TESTS=1 with an isolated DSN (never committed).
Worktree:     detached at the reviewed feature head (b31e655) with the uncommitted RA-1C files
              overlaid; removed after the run. The shared aiagents-test stack's postgres/redis
              containers were confirmed in the same pre-existing "Exited" state before and after
              this stage -- untouched throughout.
```

## Canonical manifest generation (M-2B, §8)

Each of `shared/sdk/backup_dr/migration_manifests/{031,032,033,034,035}.json` was produced by an
ad-hoc, NOT-committed generator script run once against a clean isolated PostgreSQL 16 database
(baseline 029/030 only, then 031-035 applied in order, one at a time), using the SAME
`schema_fingerprint()` function `migration_runner.py` itself uses for `canonical_semantic_fingerprint`
-- guaranteeing the manifest is directly `==`-comparable with what the runner computes at apply/
plan time. Connected PostgreSQL major version confirmed 16 for all five. Each manifest's
`owned_objects` was cross-checked to equal the runner's own `MIGRATION_FINGERPRINT_TABLES`/
`MIGRATION_CREATED_TABLES` catalog for that filename (enforced permanently by `_load_manifest`,
not just at generation time). The manifests were reviewed for content (spot-checked column/
constraint/index lists against the migration SQL) before being committed.

## Results

### New: RA-1C ledger/schema consistency and CLI redaction closure (real PostgreSQL 16)

```text
tests/test_step66c4_be3_ra1c_ledger_schema_cli.py -> 31 passed / 0 skipped / 0 failed
```

Coverage, matching every §17-mandated scenario:

**M-2A (ledger/schema consistency):**
- `test_pg_ledger_applied_but_table_absent_plan_and_apply_fail_closed`: a raw isolated-rehearsal
  "down" of migration 035 (table dropped) after a full ledger-aware apply -- `plan_chain` reports
  `drift_status["035"] == "ledger_schema_mismatch"`, `current_version != "035"`, and
  `result_code != "success"`; `apply_chain_with_ledger` raises `LedgerSchemaMismatchError`; the
  table is confirmed STILL absent afterward (no silent recreate).
- `test_pg_ledger_applied_but_table_wrong_shaped_fails_closed`: a column dropped (table still
  exists, wrong shape) is detected the same way; the raised exception's
  `.ra1c_diagnostic_code == "ledger_schema_mismatch"`.
- `test_pg_ledger_applied_missing_index_detected_as_drift`: a plain (non-unique-constraint-backed)
  index dropped is detected as `ledger_schema_mismatch` on both plan and apply.
- `test_pg_ledger_applied_changed_fk_action_detected_as_drift`: an FK's `ON DELETE` action changed
  (RESTRICT to CASCADE) on migration 031's table is detected.
- `test_pg_ledger_applied_changed_check_expression_detected_as_drift`: a CHECK constraint's
  expression body changed (same name, different bound) is detected.
- `test_pg_ledger_reconciled_row_also_reverified_against_schema`: a `reconciled_after_ambiguous_
  commit` row is NOT exempt from the same re-check -- dropping its table afterward is still caught
  by a subsequent `plan_chain` call.

**Raw down policy (§5-6):**
- `test_pg_raw_isolated_down_produces_mismatch_not_silent_success`: the full chain applied via the
  ledger, then all five `*_down.sql` files run in reverse (raw, outside the runner) -- `plan_chain`
  reports `result_code != "success"` and `drift_status["031"] == "ledger_schema_mismatch"`;
  `apply_chain_with_ledger` raises `LedgerSchemaMismatchError`; the table is confirmed still absent
  (never silently recreated).
- `test_pg_destroy_recreate_then_clean_apply_succeeds`: after the same raw-down sequence, dropping
  the ledger and baseline too (simulating "destroy the ephemeral database/container") and rebuilding
  from a clean baseline succeeds cleanly -- `result_code == "success"`, all five versions applied.

**Manifest validation (§9, all fail closed):**
- `test_pg_missing_manifest_fails_closed`: `MANIFESTS_DIR` pointed at an empty directory ->
  `MigrationManifestError` ("MISSING").
- `test_pg_manifest_wrong_filename_fails_closed` / `..._wrong_version_fails_closed` /
  `..._wrong_sql_checksum_fails_closed` / `..._wrong_postgres_major_fails_closed`: each field
  tampered independently in an isolated manifest copy (via `monkeypatch.setattr(runner,
  "MANIFESTS_DIR", ...)`) -> `MigrationManifestError` in every case, with a message identifying the
  mismatched field.
- `test_pg_manifest_wrong_fingerprint_detected_after_apply`: a tampered
  `canonical_semantic_fingerprint` is detected AFTER the migration SQL runs (the only field that
  can't be checked before DDL) -> `SchemaDriftError`, not a silent "applied."

**Ambiguous commit reconciliation (§17 "Ambiguous commit"):**
- `test_pg_ambiguous_commit_reconciles_with_exact_expected_fingerprint`: DDL applied out-of-band,
  matching `applying` ledger row inserted WITH the real manifest's `canonical_semantic_fingerprint`
  as `expected_fingerprint` -> reconciles.
- `test_pg_ambiguous_commit_wrong_shaped_table_rejected`: same setup, but the table is altered
  (CHECK constraint dropped) before reconciliation is attempted -> `SchemaDriftError`.
- `test_pg_ambiguous_commit_null_expected_fingerprint_rejected`: an `applying` row with NO
  `expected_fingerprint` at all -> `ExpectedFingerprintMissingError` (the exact RA-1FC-identified
  gap).
- `test_pg_ambiguous_commit_manifest_checksum_mismatch_rejected`: a matching, non-null expected
  fingerprint, but the manifest consulted at reconciliation time has a tampered checksum ->
  `MigrationManifestError`, reconciliation refused.

**M-3A (DSN/secret redaction, parametrized over 8 messages):**
- `test_redact_for_operator_covers_every_dsn_scheme_and_credential_field`: `postgres://`,
  `postgresql://`, `postgresql+asyncpg://`, `redis://`, `rediss://`, an `https://...?token=...`
  query-string credential, and bare `password=`/`dsn=` fields -- in every case the secret,
  username, host, and database name are confirmed ABSENT from the redacted output.
- `test_redact_for_operator_leaves_ordinary_messages_intact`: a genuinely non-secret-shaped message
  passes through byte-for-byte unchanged (no false-positive over-redaction).

**M-3B (CLI connect-failure contract):**
- `test_cli_plan_with_unreachable_dsn_exits_1_one_json_no_traceback_no_dsn` /
  `test_cli_apply_with_unreachable_dsn_exits_1_one_json_no_traceback_no_dsn`: both modes, against
  an unreachable DSN carrying a dummy username/password, exit 1, print exactly one JSON object to
  stderr (`result_code: "database_connect_failed"`), stdout is empty, and neither stdout nor
  stderr contains the dummy username, dummy password, the host:port, or the word "Traceback."
- `test_cli_plan_success_prints_exactly_one_stdout_json_object`: a healthy `--plan` invocation
  prints exactly one JSON object to stdout, `result_code: "success"`, stderr empty.

**Regression sanity (within the same suite):**
- `test_pg_full_chain_apply_all_manifests_present_and_valid`: the full 031-035 chain still applies
  cleanly end to end with all five manifests present and valid; every ledger row's
  `expected_fingerprint == observed_fingerprint`; a duplicate invocation re-applies nothing
  (ledger-authoritative fast path preserved).

### Regression (real PostgreSQL 16, same isolated container)

```text
tests/test_step66c4_be3_ra1_migration_rehearsal.py +
tests/test_step66c4_be3_ra1b_migration_runner_remediation.py +
tests/test_step66c4_be3_ra1c_ledger_schema_cli.py +
tests/test_step66c4_be1_data_model_deadline_outbox.py +
tests/test_step66c4_be1_r1_remediation.py
-> 125 passed / 0 skipped / 0 failed
```

Three of RA-1B's OWN tests required an update (not a weakening -- see the remediation record §7
for the full reasoning): two ambiguous-commit tests now insert the real manifest's
`canonical_semantic_fingerprint` as `expected_fingerprint` (previously they inserted none, which is
exactly the null-expectation gap M-2B closes); one fault-injection test now supplies an isolated,
monkeypatched manifest copy matching its synthetic broken-SQL filename, so the DDL-failure path it
tests is still reached rather than being short-circuited by the new manifest-filename check. All
three continue to assert exactly what they originally asserted.

```text
Full step66c4-tagged suite -> 380 passed / 5 skipped / 3 failed / 4884 deselected.
```

The 3 failures are the SAME three pre-existing failures identified by RA-1A and reconfirmed
unchanged by every subsequent stage (RA-1B, RA-1FC):

```text
test_step66c4_be1_merge.py::test_no_live_outbox_producer_on_main -- stale BE1-M historical verifier
  predating BE3's already-merged replay/resume modules.
test_step66c4_be3_planning.py::test_no_backend_api_migration_frontend_deployment_code_changed --
  stale BE3-P planning-stage git-diff guard vs. an old baseline ref.
test_step66c4_be3_runtime_activation_planning.py::test_verifier_script_passes -- this remote host's
  PATH has no bare "python" (pre-existing environment quirk).
```

Count reconciliation: main@18f11fe = 314 passed; feature@b31e655 (pre-RA-1C) = 349 passed (314 +
12 RA-1A + 23 RA-1B); feature + RA-1C = 380 passed (349 + 31 new RA-1C tests) -- exactly accounted
for, no unexplained gain or loss. No new failure, no additional skip, no assertion weakened.

## Quality gates

```text
ruff check (changed Python files):    PASS
black --check (changed Python files): PASS (2 files auto-reformatted, then re-verified passing)
mypy (changed modules):               PASS
git diff --check:                     PASS (only benign LF/CRLF conversion notices, no error)
Secret / internal-identifier scan of committed files: PASS
scripts/verify_step66c4_be3_ra1c_ledger_schema_cli.py: PASS
```

## Posture

```text
M-2A: CLOSED -- applied/reconciled ledger rows are re-verified against the actual schema every
      time, via the committed canonical manifest, in both plan_chain and apply_chain_with_ledger.
M-2B: CLOSED -- expected_fingerprint is now sourced from a committed, pre-DDL canonical manifest,
      never learned after the fact; reconciliation requires a non-null, manifest-validated match.
M-3A: CLOSED -- redaction covers every DSN/connection-string scheme this project uses plus bare
      userinfo and key=value credential fields, collapsing the whole message on detection.
M-3B: CLOSED -- the CLI's connect attempt is wrapped in a protected path; a connect failure always
      prints exactly one redacted JSON object and exits non-zero, never a raw traceback.
Migrations 031-035: UNCHANGED. Review branch 9cd841f: UNCHANGED, unmerged. H-1/M-1: unmodified.
Shared/test/staging/production database: untouched. All four BE3 feature gates: unaffected by this
  stage (unchanged, still default-false). Worker/relay/consumer: none started.
production_executed_true_count: 0.
Next: a second focused closure by the original RA-1R reviewer over M-2A/M-2B/M-3A/M-3B before
  Gates 1/2/6 may be marked CLOSED. Draft PR #21 remains Draft/OPEN/NOT FOR MERGE.
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
