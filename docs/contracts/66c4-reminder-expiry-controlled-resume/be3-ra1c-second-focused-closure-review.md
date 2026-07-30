# Step 66C.4-BE3-RA-1FC2 — Second Focused Closure Review (M-2A / M-2B / M-3A / M-3B)

> **Independent second focused-closure review by the ORIGINAL RA-1R / RA-1FC reviewer (continuity),
> NOT the RA-1C implementation session. Scope is EXACTLY M-2A/M-2B/M-3A/M-3B — no re-run of the full
> RA-1 review. Every conclusion is re-derived from the committed `migration_runner.py` (7820b4b), the
> CLI, the committed manifests, and direct experiments against a fresh isolated ephemeral PostgreSQL
> 16 — not from RA-1C's own self-verifier. Authorizes NO shared migration, NO deployment, NO
> activation, NO merge; modifies no implementation file, manifest, or test under review.**

## Markers (never conflated)

```text
Process marker (artifacts/process complete): STEP66C4_BE3_RA1C_SECOND_FOCUSED_CLOSURE_VERIFY: PASS
Technical verdict (independent judgment):     RA1_TECHNICAL_VERDICT: REMEDIATION_REQUIRED
```

## Per-finding verdict

```text
M-2A  Applied ledger versus actual schema consistency ......... CLOSED
M-2B  Canonical expected-fingerprint manifests + reconciliation  CLOSED
M-3A  DSN and credential redaction ............................ CLOSED
M-3B  CLI protected connection and single-JSON error contract .. REMEDIATION_REQUIRED (narrow, Low)
```

Three of the four findings are strongly and completely closed. M-3B's originating defect — the CLI
connect path raising a raw traceback — is fully fixed, but a strict reading of the closure spec §17
shows the CLI's **missing-configuration** path still emits a plain-text line rather than the required
single JSON object. Because §26 forbids closing the "CLI error-output contract" as PASS_WITH_GAPS,
M-3B cannot be certified fully closed, so the overall technical verdict is **REMEDIATION_REQUIRED**.
This is a single, Low-severity, one-line residual (no secret, no traceback, correct exit code 2); the
substantive M-3B risk is gone.

## Scope reviewed

```text
Canonical main:                18f11fe
RA-1B head (prior review):     b31e655
RA-1C remediation head:        7820b4b   (PR #21 Draft/OPEN/unmerged — confirmed before and after)
Original review head:          9cd841f   (RA-1FC; preserved, unmodified)
Reviewer-only integration:     07f839f   (merge of 7820b4b into the review branch; NOT FOR MAIN)
Focused remediation diff:      b31e655..7820b4b  (migration_runner.py +356 net; CLI +51; five new
                               committed manifests; +31 tests; three RA-1B tests adjusted;
                               migrations 029-035 UNCHANGED)
```

All PostgreSQL work ran on a fresh isolated ephemeral PostgreSQL 16.14 container on an internal test
runtime (distinct container name and port from every prior RA-1 stage), destroyed after the review.

---

## M-2A — CLOSED

`plan_chain` and `apply_chain_with_ledger` now treat `applied` **and**
`reconciled_after_ambiguous_commit` rows identically: they re-validate the committed canonical
manifest and recompute the owned-object fingerprint, requiring it to equal
`manifest.canonical_semantic_fingerprint` — not merely that the file checksum is unchanged. Any
missing/altered/wrong-shaped object fails closed (`LedgerSchemaMismatchError` on apply;
`drift_status == "ledger_schema_mismatch"` and a non-`success` plan `result_code` on plan).

Independently reproduced (my `test_m2a_*`), all eight required §4 cases fail closed:

```text
ledger=applied + table absent (DROP TABLE)            -> plan ledger_schema_mismatch; apply raises
ledger=applied + column absent (DROP COLUMN)          -> plan ledger_schema_mismatch; apply raises
ledger=applied + index absent (DROP INDEX)            -> plan ledger_schema_mismatch; apply raises
ledger=applied + CHECK expression changed             -> plan ledger_schema_mismatch; apply raises
ledger=applied + FK ON DELETE changed                 -> plan ledger_schema_mismatch; apply raises
ledger=applied + FK ON UPDATE changed                 -> plan ledger_schema_mismatch; apply raises
ledger=applied + wrong target table shape (extra col) -> plan ledger_schema_mismatch; apply raises
ledger=reconciled_after_ambiguous_commit + later drift-> plan ledger_schema_mismatch; apply raises
```

In every case there is no silent skip, no object auto-recreation, and no later-migration execution.

§5 raw-down lifecycle (`test_m2a_raw_down_then_plan_and_apply_fail_closed_then_fresh_db_reapply`):

```text
clean ledger apply 031-035 -> raw isolated down 035-031:
  plan.result_code == "ledger_schema_mismatch"; every version flagged ledger_schema_mismatch;
    current_version is NOT falsely "035"; pending is not reported as healthy.
  apply -> LedgerSchemaMismatchError (non-zero); the dropped tables are NOT recreated.
  ledger rows still say 'applied' -- never silently edited or auto-rolled-back.
destroy DB -> recreate -> baseline 029/030 -> apply 031-035 -> clean success (only the fresh-DB path
  can rehearse again). This is exactly the intended contract.
```

§6 shared-rollback policy: the RA-1C record §3 states explicitly that **ledger-managed destructive
down is NOT supported for shared environments**, and prescribes the shared rollback strategy (disable
gates → stop poller/relay/consumer → roll back the application version → retain migration tables and
business data → forward-fix under separate authorization). The runner deliberately exposes **no**
down/rollback/`mark-as-rolled-back`/ledger-edit affordance (confirmed by source inspection), and the
plan's mismatch op-line surfaces `recreate_ephemeral_database_or_use_forward_fix`. None of the §6
prohibited paths (manual ledger deletion/edit, blind down/reapply, automatic mark-as-rolled-back)
exist. M-2A is closed.

## M-2B — CLOSED

Five committed manifests (`shared/sdk/backup_dr/migration_manifests/{031..035}.json`) each carry the
seven required fields with correct values (independently verified: `migration_sha256` equals the
on-disk file checksum, `postgres_major_version == 16`, `manifest_format_version == 1`, and
`owned_objects` equals the runner's own catalog). Owned-object boundary is correctly scoped: 031 owns
`{clarification_lifecycle_outbox, operator_clarification_requests}` (it ALTERs the latter); 032-035
each own only their single created table — so altering an unrelated migration's table does not
falsely fail another migration's validation (verified: the per-case fail-closed tests only flag the
migration that owns the mutated object).

Provenance and immutability (`test_m2b_*`, plus source inspection):

```text
manifests are committed files; the runner has NO write/regenerate path -- no generate_if_missing,
  refresh_manifest, learn_current_schema, accept_observed_as_expected, .write_text, or json.dump.
missing manifest / invalid JSON / format mismatch / owned-object mismatch  -> MigrationManifestError
on-disk checksum != manifest checksum                                      -> MigrationManifestError
unsupported or connected-server-mismatched PostgreSQL major version        -> MigrationManifestError
```

Pre-DDL expected fingerprint (`test_m2b_expected_fingerprint_recorded_before_ddl`): injecting a
failure at the moment the migration SQL would run (after the `applying` row is committed) shows the
ledger row already carries `expected_fingerprint` (= the manifest fingerprint) plus filename and
checksum — the expectation is recorded BEFORE any DDL, never learned afterward. Post-apply, the
observed owned-object fingerprint is required to equal the expected, else `fingerprint_mismatch` /
drifted and the chain stops.

Strict ambiguous-commit reconciliation (`test_m2b_ambiguous_reconcile_strict_matrix`): reconciles
ONLY when everything matches; each single deviation is rejected:

```text
correct schema + matching expected fingerprint  -> reconciled_after_ambiguous_commit
expected_fingerprint IS NULL                     -> ExpectedFingerprintMissingError
wrong-shaped table (extra column)                -> SchemaDriftError
missing index                                    -> SchemaDriftError
changed CHECK expression                         -> SchemaDriftError
recorded expected fingerprint != manifest        -> SchemaDriftError
```

This directly closes the RA-1FC M-2B gap (previously a wrong-shaped table with a null expected
fingerprint was reconciled as good). M-2B is closed.

## M-3A — CLOSED

`redact_for_operator` no longer relies on a single substring marker. `_looks_secret_shaped` detects
every connection-string scheme this project uses (`postgres`/`postgresql`/`postgresql+asyncpg`/
`redis`/`rediss`/`http(s)`), a bare `user:password@host` userinfo fragment, and key=value credential
fields (password/passwd/secret/token/apikey/api_key/dsn), and collapses the ENTIRE message to a
fixed endpoint-free string on any detection. Independently verified (`test_m3a_*`):

```text
every listed scheme with user:pass@host:port/db  -> collapsed; none of {password, host, username,
                                                    port, database} survives in the output
?password= / ?secret= / ?token= / ?apikey= / ?api_key= / password= / token: / dsn=  -> collapsed
bare "user:password@host" (no scheme)            -> collapsed
diagnostic codes (database_connect_failed, migration_checksum_mismatch, ledger_schema_mismatch,
  untracked_schema, expected_fingerprint_missing)  -> preserved verbatim (never clobbered)
```

This closes the RA-1FC M-3 gap (the canonical `postgresql://` scheme was previously unredacted).

Observation (not a gap): `redact_for_operator` collapses on *credential-shaped* content, so a bare
non-credential host message like `connection to host:port failed` would pass through unredacted.
However the CLI never routes connect-error text to operator output at all (see M-3B: the connect
failure emits a fixed message with no exception text), so no host/port/database ever leaks through the
CLI. §15's host-hiding requirement is conditional on the operator contract; the RA-1C contract
achieves it by omission at the CLI boundary, which I verified end-to-end. M-3A is closed.

## M-3B — REMEDIATION_REQUIRED (narrow, Low severity)

The originating M-3B defect is fully fixed and independently verified. `_connect_or_none` wraps
`asyncpg.connect()` in `try/except BaseException`; a connect failure calls `_print_connect_failure`,
which prints exactly one JSON object (`result_code: "database_connect_failed"`) to stderr with the
underlying exception text **deliberately omitted entirely**, and exits 1. Verified for both `--plan`
and `--apply` across malformed / unreachable-host / authentication-failure DSNs
(`test_m3b_connect_failures_single_json_no_secret`):

```text
exit code = 1; stdout empty; stderr = exactly one JSON object; no traceback; none of
  {password, host, username, port, database} present. Holds even with PYTHONASYNCIODEBUG=1.
success --plan / --apply: exit 0; stdout = exactly one JSON object (mode/result_code/current_version/
  target_version/applied_versions/reconciled_versions/failed_version); stderr empty.
```

Residual (spec §17): the **missing-configuration** path (`_dsn_from_env`, when
`PLATFORM_MIGRATIONS_DATABASE_URL` is unset) prints a plain-text line
(`"PLATFORM_MIGRATIONS_DATABASE_URL is not set; refusing to run."`) to stderr and exits 2. This meets
"exit code = 2" and "no traceback" and leaks no secret, but it is **not** the single JSON object §17
explicitly requires for missing configuration (verified: the stderr does not parse as JSON). Because
§26 bars closing the CLI error-output contract as PASS_WITH_GAPS, M-3B is marked
REMEDIATION_REQUIRED. Severity is Low: it is a one-line fix (`_dsn_from_env` should emit a JSON object
such as `{"result_code": "missing_configuration", ...}` before `sys.exit(2)`), affects only the
DSN-unset path, and carries no secret/traceback exposure.

## Test-update integrity (spec §20)

RA-1C adjusted three RA-1B tests. Independently reviewed (`test_s20_*` plus direct diff inspection);
none is substantively weakened — each only adapts the fixture to the new, STRICTER manifest/
expected-fingerprint contract:

```text
test_pg_ambiguous_commit_reconciles_when_schema_matches
  before: inserted an 'applying' row with NO expected_fingerprint (null).
  after:  inserts the real manifest's canonical_semantic_fingerprint as expected_fingerprint.
  reason: RA-1C now REQUIRES a non-null expected fingerprint to reconcile (the exact null-gap being
          closed); the reconcile assertion is unchanged. Coverage preserved, not weakened.

test_pg_partial_schema_in_applying_state_rejected_as_drifted
  before: 'applying' row with null expected_fingerprint; assert SchemaDriftError.
  after:  same, WITH expected_fingerprint set from the manifest; still assert SchemaDriftError.
  reason: without the expected fingerprint the row would now trip ExpectedFingerprintMissingError
          first, masking the intended "incomplete schema -> drifted" path; supplying it isolates the
          original assertion. Coverage preserved.

test_pg_failed_migration_ledger_state_recorded
  before: wrote a synthetic broken 032 file; assert PostgresError + ledger 'failed'.
  after:  additionally builds an ISOLATED copy of the manifests dir whose 032 manifest filename+
          checksum match the synthetic file, and monkeypatches MANIFESTS_DIR to it, so RA-1C's
          manifest-filename check does not short-circuit before the DDL-failure path under test.
  reason: a test-fixture accommodation; the assertion (PostgresError + status 'failed', secret-free
          error_code) is unchanged; no production guard is disabled for the assertion. Coverage
          preserved.
```

No xfail, no skip, no broad exception swallow, no removed negative case, no relaxed substring-only
success check. §20 passes.

## Regression (independently re-run on both commits)

```text
baseline 18f11fe:  3 failed / 314 passed / 5 skipped   (step66c4-tagged)
feature  7820b4b:  3 failed / 396 passed / 5 skipped   (= 314 + 12 RA-1A + 23 RA-1B + 31 RA-1C + 16 this)
```

Same three pre-existing failures (identical node IDs, unchanged root causes: the stale BE1-M and
BE3-P historical guards, and the PATH-dependent bare-`python` verifier subprocess), none
migration/backup/CLI-related, none introduced by RA-1C. No new feature-only failure, no additional
skip (5 on both), no assertion weakened; both BE1 allowlist guards PASS on feature. Directly affected
RA-1 suites (RA-1A + RA-1B + RA-1C + this closure): **82 passed / 0 failed / 0 skipped**.

## Conclusion

M-2A, M-2B, and M-3A are independently confirmed CLOSED — the ledger now re-verifies actual schema
against committed manifests (raw-down and every out-of-band mutation fail closed), the expected
fingerprint is provenance-anchored in committed manifests and recorded before any DDL with strict
reconciliation, and redaction covers every DSN scheme with a whole-message collapse. M-3B's
substantive defect (connect-path traceback) is closed, but the missing-configuration path does not
emit the §17-required single JSON object, so — under the spec's own §26 gate — the technical verdict
is **REMEDIATION_REQUIRED** on that single Low-severity residual. This verdict applies only to
migration-runner shared-apply readiness; it authorizes no shared migration, deployment, or activation.

---
_Non-production only. No production action. No production data. Neutral labels only — no internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets ("internal test runtime", "isolated ephemeral PostgreSQL 16")._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
