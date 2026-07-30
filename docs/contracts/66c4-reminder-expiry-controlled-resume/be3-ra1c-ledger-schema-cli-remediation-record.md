# Step 66C.4-BE3-RA-1C — Ledger–Schema Consistency and CLI Redaction Closure

> **Remediation record. Closes M-2A, M-2B, M-3A, M-3B from the Step 66C.4-BE3-RA-1FC focused
> closure (performed by the original RA-1R reviewer over the RA-1B remediation). Performed by the
> original RA-1A/RA-1B implementation session, per this stage's own instruction. H-1 and M-1
> (already CLOSED by RA-1FC) are unmodified. NOT applied to any shared database. NOT deployed. NOT
> activated. Draft PR #21 remains Draft/OPEN/NOT FOR MERGE. Migrations 029-035 are UNCHANGED.**

## 1. Baseline confirmed

Before any implementation change: `origin/feature/66c4-be3-ra1-migration-rehearsal` = `b31e655`,
`origin/review/66c4-be3-ra1-migration-rollback` = `9cd841f` (the RA-1FC focused-closure commit),
PR #21 Draft/OPEN/unmerged, working tree clean — all confirmed per this stage's own §1.

## 2. M-2A — applied/reconciled ledger row never re-checked against the actual schema

**Finding (RA-1FC §13/§9):** `apply_chain_with_ledger` and `plan_chain` treated an `applied` (or
`reconciled_after_ambiguous_commit`) ledger row as healthy once the on-disk file checksum matched —
they never re-verified that the *actual* schema still existed or still matched. A raw isolated
"down," a dropped index, or an altered CHECK/FK action left the ledger silently claiming health.

**Fix.** Both `plan_chain` and `apply_chain_with_ledger` now, every time an `applied` or
`reconciled_after_ambiguous_commit` row is encountered:

```text
1. checksum matches file on disk (unchanged check)
2. load + validate the migration's canonical manifest (filename/checksum/PG-major/format-version)
3. recompute the CURRENT owned-object schema fingerprint
4. require fingerprint == manifest.canonical_semantic_fingerprint
```

Any failure at step 2 raises `MigrationManifestError`; any failure at step 4 raises
`LedgerSchemaMismatchError` (apply) or sets `drift_status[version] = "ledger_schema_mismatch"`
(plan) — never silently treated as healthy, never blindly reapplied. `plan_chain`'s per-version
`current_version` is never set to a version failing this check, and the new top-level
`MigrationPlan.result_code` surfaces the first non-healthy status so `--plan` exits non-zero.

Verified directly: table absent, table wrong-shaped (column dropped), index missing, FK action
changed, CHECK expression changed, and a `reconciled_after_ambiguous_commit` row later drifting —
all six independently fail closed (see evidence record).

## 3. Destructive-down policy (§5–6)

**Decision, recorded explicitly:** Ledger-managed destructive down is **NOT supported** for shared
environments. This was a policy gap RA-1FC's §13 required an explicit answer to; the answer is
option **B** from this stage's own spec:

```text
Shared rollback strategy (future, once shared apply is ever authorized):
  disable feature gates -> stop poller/relay/consumer -> roll back the APPLICATION version ->
  RETAIN migration tables and business data -> forward-fix under separate authorization.

Isolated rehearsal down (RA-1A's own pre-activation down rehearsal) remains valid ONLY as an
ephemeral, no-business-data, explicit-rehearsal-mode exercise. It is not, and must never be
described as, a safe production/shared rollback mechanism.
```

Concretely: after a raw isolated-rehearsal `*_down.sql` runs against an ephemeral database whose
ledger already recorded the chain as applied, M-2A's re-verification (§2 above) is what makes
"ledger/schema mismatch is expected" a real, enforced property rather than a documentation-only
promise — `plan` reports `ledger_schema_mismatch` (not `ok`), `apply` raises
`LedgerSchemaMismatchError` and exits non-zero, and nothing is silently recreated. The only
supported recovery from that state is exactly what this stage's §6 requires: destroy the ephemeral
database/container, create a fresh one, and rerun the baseline + full migration chain from scratch
— never `DELETE FROM platform_schema_migrations`, never manual ledger editing, never a blind
reapply. Both are verified directly (see evidence record).

The runner never implements a `down`/rollback operation of its own — this is intentional, not an
oversight: providing one would invite exactly the "ledger-managed destructive down" pattern this
stage explicitly rules out for shared use.

## 4. M-2B — ambiguous-commit reconciliation had no trustworthy expected fingerprint

**Finding (RA-1FC §12):** `existing["expected_fingerprint"] not in (None, observed)` treated a
*null* expected fingerprint as an automatic match — an ambiguous "applying" row with no recorded
expectation at all could be silently reconciled.

**Fix.**

- **Committed canonical manifests**: `shared/sdk/backup_dr/migration_manifests/{031,032,033,034,
  035}.json`, one per migration, each produced ONCE from a clean, isolated, ephemeral PostgreSQL 16
  rehearsal (baseline 029/030 + that migration only) and committed after this session's own review
  — never generated from, or trusted from, the database currently being checked. Each manifest
  records `migration_version`, `migration_filename`, `migration_sha256`, `postgres_major_version`
  (16), `owned_objects` (the same table set the runner's own `MIGRATION_FINGERPRINT_TABLES`/
  `MIGRATION_CREATED_TABLES` catalog already used), `canonical_semantic_fingerprint` (the exact
  `schema_fingerprint()` output for those tables, serialized identically to how the runner computes
  it, so the two are directly `==`-comparable), and `manifest_format_version` (1).
- **Validation** (`_load_manifest` + `_validate_manifest`): missing file, invalid JSON, unrecognized
  format version, mismatched `migration_version`/`migration_filename`/`owned_objects` (cross-checked
  against the runner's own catalog), mismatched on-disk checksum, an unsupported or
  connected-server-mismatched PostgreSQL major version — every one of these raises
  `MigrationManifestError` and fails closed. The manifest is never regenerated or overwritten
  automatically.
- **Expected fingerprint before DDL**: `_insert_applying_row` now takes and stores
  `expected_fingerprint` (from the manifest) at INSERT time, before `apply_migration_file` ever
  runs. `_mark_applied` only ever writes `observed_fingerprint` — it never touches
  `expected_fingerprint` again.
- **Stricter reconciliation**: an ambiguous `applying` row can now only reconcile if ALL of: version/
  filename/checksum match (unchanged), `expected_fingerprint IS NOT NULL` (`ExpectedFingerprintMissingError`
  if null — the exact gap RA-1FC found), the manifest itself validates AND its
  `canonical_semantic_fingerprint` still equals the ledger's recorded `expected_fingerprint`
  (`SchemaDriftError` otherwise — catches a manifest that drifted out from under an in-flight
  attempt), the target schema is complete, and the observed fingerprint matches. A wrong-shaped
  table is rejected the same way it always was — via the fingerprint comparison — but the
  comparison itself is now against a value that was fixed BEFORE the DDL ran, not learned after.

Verified directly: a correct schema with a matching non-null expected fingerprint reconciles; a
wrong-shaped table with an otherwise-matching row is rejected; a null `expected_fingerprint` is
rejected; a tampered/mismatched manifest checksum during reconciliation is rejected.

## 5. M-3A — DSN and secret redaction incomplete

**Finding (RA-1FC's own source inspection):** `_FORBIDDEN_VALUE_MARKERS` contained `"postgres://"`
but not the canonical `"postgresql://"` scheme (nor `"postgresql+asyncpg://"`, `"rediss://"`,
`"https://user:pass@..."`), so a `postgresql://` DSN passed through unredacted.

**Fix.** Detection is no longer a fixed substring list. `redact_for_operator` now collapses the
ENTIRE message to a fixed, endpoint-free string whenever ANY of the following is detected:

```text
_SECRET_SCHEME_RE   postgres:// | postgresql:// | postgresql+asyncpg:// | redis:// | rediss:// |
                    http(s)://          (case-insensitive)
_SECRET_USERINFO_RE a bare "user:password@host" fragment, even with no recognized scheme prefix
_SECRET_KV_RE       password|passwd|secret|token|apikey|api_key|dsn  followed by  :  or  =
```

A whole-message collapse (rather than a targeted in-place substitution) was chosen deliberately:
a partial substitution risks leaving an unanticipated fragment (a different scheme, a query-string
token the regex didn't anticipate) exposed; collapsing the whole message cannot leak anything the
detector missed inside the SAME message, only a category the detector fails to recognize at all —
which is exactly why the detector itself was broadened to cover every scheme this project uses
rather than trying to enumerate substrings after the fact.

Verified directly (parametrized): `postgres://`, `postgresql://`, `postgresql+asyncpg://`,
`redis://`, `rediss://`, an `https://...?token=...` query-string credential, and bare
`password=`/`dsn=` fields — in every case the secret, username, host, and database name are all
absent from the redacted output; an ordinary non-secret-shaped message is left byte-for-byte
intact (no false-positive over-redaction).

## 6. M-3B — CLI connect failure did not match the redacted single-JSON contract

**Finding (RA-1FC's own source inspection):** both `asyncpg.connect(dsn=dsn)` calls in
`scripts/run_platform_migrations.py` sat OUTSIDE their respective `try` blocks — a connect failure
(which routinely echoes the DSN, host, port, and database name from asyncpg/libpq) raised a raw,
unredacted traceback instead of the documented single-JSON, redacted, non-zero-exit contract.

**Fix.** Both `--plan` and `--apply` now call a new `_connect_or_none(dsn)` helper that wraps
`asyncpg.connect` in its own `try`/`except BaseException`. On failure, `_print_connect_failure(mode)`
prints exactly ONE JSON object to stderr and returns exit code 1:

```json
{
  "result_code": "database_connect_failed",
  "mode": "plan",
  "success": false,
  "message": "Database connection failed.",
  "failed_version": null
}
```

The underlying exception text is deliberately NOT included at all here (not even through
`redact_for_operator`) — a connect failure is the highest-risk path for DSN/credential leakage, so
this never depends on the redactor catching every possible phrasing. `--plan`'s success/failure
result (via the new `MigrationPlan.result_code`) and `--apply`'s exception payload (now also
carrying `migration_version`/`ledger_status`/`expected_fingerprint`/`observed_fingerprint`/
`diagnostic_code` from the `.ra1c_*` attributes attached in `migration_runner.py`) print to stdout
on success and stderr on failure respectively — never both in the same invocation.

Verified directly: `--plan`/`--apply` against an unreachable/invalid DSN each exit 1, print exactly
one parseable JSON object to stderr (stdout empty), contain no traceback and no DSN/username/
password substring; `--plan` against a healthy database prints exactly one JSON object to stdout
(stderr empty) and exits 0.

## 7. Scope discipline

```text
Modified:   shared/sdk/backup_dr/migration_runner.py, scripts/run_platform_migrations.py
            (both allowed changes)
Added:      shared/sdk/backup_dr/migration_manifests/{031,032,033,034,035}.json,
            tests/test_step66c4_be3_ra1c_ledger_schema_cli.py, this record, the evidence record,
            the handoff record, the self-verifier
Also fixed: tests/test_step66c4_be3_ra1b_migration_runner_remediation.py -- three of RA-1B's OWN
            tests needed adjustment because the new manifest-filename binding (a deliberate,
            necessary part of M-2B) legitimately changed what they had to set up: two tests
            (`test_pg_ambiguous_commit_reconciles_when_schema_matches`,
            `test_pg_partial_schema_in_applying_state_rejected_as_drifted`) manually inserted an
            'applying' ledger row WITHOUT an expected_fingerprint -- exactly the null-expectation
            gap M-2B closes -- so they now insert the real manifest's
            canonical_semantic_fingerprint, continuing to exercise their ORIGINAL assertions
            (reconciliation succeeds / incomplete-schema drift is rejected) rather than being
            short-circuited by the new (correct) ExpectedFingerprintMissingError; one test
            (`test_pg_failed_migration_ledger_state_recorded`) injects a synthetic, differently-
            named broken-SQL file for fault injection and now supplies an isolated, monkeypatched
            manifest copy whose filename/checksum match that synthetic file, so the DDL-failure
            path it actually tests is still reached. No assertion was weakened or removed in any
            of the three; each still proves exactly what it originally proved.
NOT touched: migrations/029-035 (unchanged; no defect was found in them), any BE3 runtime service,
            any feature-gate default, any deployment configuration, any Compose/Helm/Kubernetes
            runtime value, any file from the RA-1R/RA-1FC review branch (`review/66c4-be3-ra1-
            migration-rollback`, up to and including its `9cd841f` focused-closure commit), H-1's
            or M-1's design (both already CLOSED; unmodified in this stage).
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
