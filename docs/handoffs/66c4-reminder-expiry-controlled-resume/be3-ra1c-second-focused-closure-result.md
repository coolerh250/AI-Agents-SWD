# Step 66C.4-BE3-RA-1FC2 → Second Focused Closure Result Handoff

> **Second focused-closure result by the original RA-1R / RA-1FC reviewer (continuity). Covers
> EXACTLY M-2A/M-2B/M-3A/M-3B over the RA-1C remediation (7820b4b). Authorizes NO shared migration,
> NO deployment, NO feature-gate change, NO activation, NO merge. Migrations 029-035, the committed
> manifests, and the RA-1C implementation were NOT modified by this closure. Gates 1/2/6 remain
> PENDING — this review does NOT close them.**

## Result

```text
Process marker:      STEP66C4_BE3_RA1C_SECOND_FOCUSED_CLOSURE_VERIFY: PASS
Technical verdict:   RA1_TECHNICAL_VERDICT: REMEDIATION_REQUIRED

M-2A  CLOSED
M-2B  CLOSED
M-3A  CLOSED
M-3B  REMEDIATION_REQUIRED (narrow, Low: missing-config path not single-JSON per spec §17)
```

The original RA-1R/RA-1FC reviewer re-derived all four findings from scratch against a fresh isolated
ephemeral PostgreSQL 16, exercising the paths RA-1C's own 31-test suite does not fully cover. M-2A,
M-2B, and M-3A are independently confirmed fully closed. M-3B's substantive defect (a raw traceback
on connect failure) is fully closed, but a single Low-severity residual remains, so the overall
verdict is REMEDIATION_REQUIRED (per the spec, all four must be closed, and the CLI error-output
contract may not be closed as PASS_WITH_GAPS).

## Findings (full detail in be3-ra1c-second-focused-closure-review.md)

```text
M-2A CLOSED. plan_chain + apply_chain_with_ledger re-verify every applied/reconciled row against the
     committed canonical manifest fingerprint (not just the file checksum). All eight §4 out-of-band
     mutation cases fail closed (plan ledger_schema_mismatch; apply LedgerSchemaMismatchError; no
     silent skip, no recreation, no later migration). Raw down -> plan/apply fail closed, tables not
     recreated, ledger not auto-edited; only a destroyed+recreated DB reapplies. Destructive-down
     policy documented; no ledger-edit/down/mark-rolled-back affordance exists.
M-2B CLOSED. Five committed, correctly-scoped canonical manifests; no runtime regeneration path;
     expected_fingerprint recorded on the applying row BEFORE any DDL; post-apply observed==expected
     required; ambiguous reconcile strictly rejects null-expected / wrong-shape / missing-index /
     changed-CHECK / tampered-expected and reconciles only an exact match. Closes the RA-1FC M-2B gap.
M-3A CLOSED. redact_for_operator detects every DSN scheme (postgres/postgresql/postgresql+asyncpg/
     redis/rediss/http(s)), bare user:pass@host userinfo, and key=value credential fields, and
     collapses the whole message; diagnostic codes survive. Closes the RA-1FC postgresql:// gap.
M-3B REMEDIATION_REQUIRED (narrow, Low). The connect-failure path now emits exactly one JSON object
     (result_code=database_connect_failed) with the exception text omitted, exit 1, no traceback, no
     secret -- verified for --plan/--apply across malformed/unreachable/auth DSNs, even under asyncio
     DEBUG. Success emits one JSON object on stdout, stderr empty, exit 0. RESIDUAL: the
     missing-configuration path (DSN unset) prints a PLAIN-TEXT line, not the single JSON object spec
     §17 requires (exit 2 and no-secret/no-traceback are correct). One-line fix; no security impact.
```

No Critical or High finding. Test-update integrity (§20): the three adjusted RA-1B tests were only
adapted to the new stricter manifest/expected-fingerprint contract; no assertion weakened, no xfail,
no skip, no swallowed exception, no removed negative case.

## What was NOT authorized, attempted, or changed

- No migration applied to any shared, test, staging, or production database.
- No implementation file, manifest, or test-under-review modified (`migration_runner.py`,
  `run_platform_migrations.py`, `migration_manifests/*`, `migrations/*`, and the RA-1A/RA-1B/RA-1C
  test suites are byte-identical to 7820b4b).
- No feature gate enabled; all four BE3 gates remain default-false.
- No deployment, no worker/relay/consumer activation, no runtime resume/replay, no production approval.
- **PR #21 (Draft/OPEN/unmerged, base=main, head=7820b4b) confirmed unchanged before and after and
  NOT merged.** The prior review commit 9cd841f was preserved unmodified. The reviewer-only
  integration merge (07f839f) exists ONLY on the review branch — NOT FOR MAIN, no PR, no
  source-of-truth claim.
- Gates 1, 2, and 6 are NOT closed by this review.

## Recommendation

```text
Required remediation before RA-1 can PASS:
  - Close M-3B: make _dsn_from_env emit a single JSON object (e.g. {"result_code":
    "missing_configuration", "mode": ..., "success": false}) to stderr before sys.exit(2), so the
    missing-configuration path matches the same single-JSON error contract as every other CLI path.
    (No other change needed; M-2A, M-2B, M-3A require nothing further.)
RA-1 readiness:  M-2A, M-2B, M-3A CLOSED; M-3B one narrow Low residual. RA-1 migration-runner
                 readiness is very close -- a single one-line CLI fix from complete.
Gates 1/2/6:     remain PENDING — not closed by this review; final status is the PM/PO's call per the
                 canonical gate definition after this closure report.
PR #21:          NOT merge-ready until the M-3B missing-config JSON residual is fixed and re-checked
                 (a trivial follow-up).
Next step:       Product-Owner decision. If the residual is remediated (or the PO explicitly accepts
                 it), this reviewer can re-check M-3B alone. No RA-2 or other stage is started here.
```

## Posture

```text
RA-1FC2: SECOND FOCUSED CLOSURE COMPLETE | M-2A CLOSED | M-2B CLOSED | M-3A CLOSED | M-3B REMEDIATION_REQUIRED
Overall: RA1_TECHNICAL_VERDICT: REMEDIATION_REQUIRED (single narrow Low residual)
Migrations 029-035 + manifests: unchanged | RA-1C implementation: unchanged | Commit 9cd841f: preserved
NOT APPLIED TO SHARED DB | NOT DEPLOYED | NOT ACTIVATED | NOT MERGED
Gates 1/2/6: PENDING (not closed by this review)
production_executed_true_count: 0
```

## Gate wording (reviewer may not self-declare shared migration complete)

```text
RA-1 migration readiness foundation:  NEARLY VERIFIED (M-2A/M-2B/M-3A closed; M-3B one Low residual)
Shared DB migration:                  NOT APPLIED
Deployment:                           NOT PERFORMED
Runtime activation:                   NOT PERFORMED
```

---
_Non-production only. No production action. No production data. Neutral labels only — no internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets ("internal test runtime", "isolated ephemeral PostgreSQL 16")._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
