# Step 66C.4-BE3-RA-1C → Second Focused Closure Handoff

> **Result handoff only. Records the outcome of the targeted M-2A/M-2B/M-3A/M-3B remediation
> following the Step 66C.4-BE3-RA-1FC focused closure. Authorizes NO shared migration, NO
> deployment, NO feature-gate change, NO merge. Draft PR #21 remains Draft/OPEN/unmerged.
> Migrations 029-035 are UNCHANGED. H-1 and M-1 are unmodified.**

## Verdict

```text
STEP66C4_BE3_RA1C_LEDGER_SCHEMA_CLI_VERIFY: PASS
```

All four findings from the RA-1FC focused closure (`RA1_TECHNICAL_VERDICT: REMEDIATION_REQUIRED`)
are closed at the implementation/self-verification level:

- **M-2A** (an applied/reconciled ledger row was never re-checked against the actual schema):
  `plan_chain` and `apply_chain_with_ledger` now recompute the owned-object schema fingerprint and
  compare it against the migration's committed canonical manifest every time such a row is
  encountered, failing closed (`LedgerSchemaMismatchError` / `drift_status ==
  "ledger_schema_mismatch"`) on any missing/altered/wrong-shaped object.
- **M-2B** (ambiguous-commit reconciliation had no trustworthy expected fingerprint): a new,
  committed, per-migration canonical manifest supplies `expected_fingerprint` BEFORE any DDL runs;
  reconciliation now requires a non-null expected fingerprint and a valid, matching manifest.
- **M-3A** (`redact_for_operator` missed `postgresql://` and other schemes): redaction now covers
  every connection-string scheme this project uses, plus bare userinfo and key=value credential
  fields, collapsing the whole message on detection.
- **M-3B** (the CLI's connect call sat outside its redacting `try`): both `--plan` and `--apply`
  now wrap the connection attempt in a protected path; a connect failure always prints exactly one
  redacted JSON object and exits non-zero, never a raw traceback.

## What was NOT authorized or attempted

- No new independent review or implementation subagent was started -- this remediation was
  performed by the original RA-1A/RA-1B implementation session, per this stage's own instruction.
- H-1 and M-1 (already CLOSED by the RA-1FC focused closure) were NOT modified.
- Migrations 029-035 were NOT modified -- no defect was found in them.
- No shared migration application, no deployment, no feature-gate enablement, no worker/relay/
  consumer activation, no runtime resume/replay/dispatch.
- The RA-1R/RA-1FC review branch (`review/66c4-be3-ra1-migration-rollback`, commit `9cd841f`) was
  NOT modified.
- Draft PR #21 was not touched, not switched out of Draft, not merged.

## Independent evidence (real PostgreSQL, not just this session's own claims)

- Isolated ephemeral PostgreSQL 16 on an internal test runtime, distinct container/port from every
  prior RA-1 stage, destroyed afterward; the shared aiagents-test stack's postgres/redis containers
  remained in their pre-existing stopped state before and after.
- Five committed canonical manifests (`shared/sdk/backup_dr/migration_manifests/{031..035}.json`),
  produced from a clean isolated rehearsal using the runner's own `schema_fingerprint()` function.
- New suite `tests/test_step66c4_be3_ra1c_ledger_schema_cli.py`: **31 passed, 0 skipped**.
- Full regression alongside RA-1A/RA-1B/BE1-allowlist suites: **125 passed, 0 skipped, 0 failed**.
- Full step66c4-tagged suite: **380 passed, 5 skipped, 3 failed** -- the same 3 pre-existing
  baseline failures every prior stage has identified, confirmed unchanged; count reconciles exactly
  (349 pre-RA-1C + 31 new RA-1C tests = 380, no unexplained gain or loss).
- Three of RA-1B's own tests were adjusted (not weakened) because the new manifest-filename/
  expected-fingerprint binding legitimately changed what they needed to set up -- see the
  remediation record for the full reasoning.
- `scripts/verify_step66c4_be3_ra1c_ledger_schema_cli.py`: PASS.
- ruff / black / mypy / `git diff --check` / secret-scan: clean.

## Destructive-down policy (recorded per this stage's own §5-6)

Ledger-managed destructive down is explicitly **NOT supported** for shared environments. Shared
rollback (if ever authorized in the future) is: disable feature gates, stop poller/relay/consumer,
roll back the application version, retain migration tables and business data, forward-fix under
separate authorization. RA-1A's isolated pre-activation down rehearsal remains valid ONLY as an
ephemeral, no-business-data exercise -- never a production/shared rollback mechanism. M-2A's
re-verification is what makes "ledger/schema mismatch is expected after a raw down" an enforced
property: `plan` reports the mismatch, `apply` fails closed, and the only supported recovery is
destroy-and-recreate the ephemeral database, never a blind ledger edit or reapply.

## Next authorized step

Per this stage's own instruction, this remediation does not itself close Gates 1/2/6 in
`be3-runtime-activation-gate.md`. The next required gate is a **second focused closure** by the
**original RA-1R independent reviewer** (not a new full review, and not this implementation
session) over M-2A, M-2B, M-3A, and M-3B -- confirming each finding is genuinely resolved, not just
self-declared resolved. That second focused closure has not been performed in this session and
requires the Product Owner to invoke it. Gates 1/2/6 remain PENDING until then. PR #21 merge and
any further RA-stage remain gated on that second focused closure plus separate, explicit Product
Owner authorization.

## Posture

```text
RA-1A: REHEARSED (self-verified) | RA-1R: independent review, RA1_TECHNICAL_VERDICT:
  REMEDIATION_REQUIRED | RA-1B: H-1/M-1/M-2/M-3 remediated (self-verified) | RA-1FC: focused
  closure, H-1/M-1 CLOSED, M-2A/M-2B/M-3A/M-3B REMEDIATION_REQUIRED | RA-1C: M-2A/M-2B/M-3A/M-3B
  remediated (self-verified)
Second focused closure by the original RA-1R reviewer: PENDING
PR: Draft #21 / NOT FOR MERGE / untouched | Review branch 9cd841f: preserved, unmerged, unmodified
Migrations 029-035: unchanged | Shared migration/deployment/activation: none
production_executed_true_count: 0
Next authorization required: second focused closure by the original RA-1R reviewer, then explicit
  PO authorization for Gates 1/2/6 closure and any further RA-stage.
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
