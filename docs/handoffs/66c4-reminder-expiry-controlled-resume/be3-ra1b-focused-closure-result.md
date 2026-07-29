# Step 66C.4-BE3-RA-1FC → Focused Closure Result Handoff

> **Focused-closure result by the original RA-1R reviewer (continuity). Covers EXACTLY H-1/M-1/M-2/M-3
> over the RA-1B remediation (b31e655). Authorizes NO shared migration, NO deployment, NO
> feature-gate change, NO activation, NO merge. Migrations 029-035 and the RA-1B implementation were
> NOT modified by this closure. Gates 1/2/6 remain PENDING — this review does NOT close them.**

## Result

```text
Process marker:      STEP66C4_BE3_RA1B_FOCUSED_CLOSURE_VERIFY: PASS
Technical verdict:   RA1_TECHNICAL_VERDICT: REMEDIATION_REQUIRED

H-1  CLOSED
M-1  CLOSED
M-2  REMEDIATION_REQUIRED
M-3  REMEDIATION_REQUIRED
```

The original RA-1R reviewer re-derived all four findings from scratch against an isolated ephemeral
PostgreSQL 16, exercising the paths RA-1B's own 23-test suite does not cover. H-1 and M-1 are
independently confirmed fully closed. M-2 and M-3 are substantially implemented but each retains one
concrete, reproduced gap, so the overall verdict is REMEDIATION_REQUIRED (per the closure spec, all
four must be closed, and ledger/down inconsistency and secret-control gaps may not be closed as
PASS_WITH_GAPS).

## Findings (full detail in be3-ra1b-focused-closure-review.md)

```text
H-1  CLOSED. Cleanup order capture->ROLLBACK->unlock->restore->re-raise ORIGINAL error; every step
     bounded/cancellation-safe and never raises; connection disposed on any cleanup failure; pool
     borrower is clean after a failure; verified incl. forced-backend-termination disposal.
M-1  CLOSED. pg_get_constraintdef + indexdef/access-method detect all 11 mutation categories,
     including FK MATCH, constraint validation-state, and index access-method (all untested by RA-1B).
M-2  REMEDIATION_REQUIRED.
     Gap A (spec §13, blocking): no coherent ledger vs. down/reapply strategy. After a raw down the
       ledger still says 'applied', plan_chain reports drift_status 'ok' / current_version='035'
       (does NOT fail closed on the ledger-vs-schema mismatch), and reapply reports SUCCESS while
       silently skipping every migration and NOT recreating the dropped tables. Neither a
       ledger-aware down (A) nor a documented fail-closed exclusion (B) exists; RA-1B docs are silent.
     Gap B (spec §12): ambiguous-commit reconcile validates only checksum + table EXISTENCE, not
       shape (expected_fingerprint is never recorded on an 'applying' row), so a wrong-shaped/tampered
       table under a matching-checksum 'applying' row is RECONCILED as good instead of failing closed.
M-3  REMEDIATION_REQUIRED.
     redact_for_operator blocks 'postgres://' but NOT the canonical asyncpg 'postgresql://' scheme,
     so that DSN form passes through unredacted; and the CLI's asyncpg.connect() is outside the
     redacting try, so a wrong-DSN connect failure prints a raw Python traceback (not the §18 redacted
     single-JSON object). No credential-VALUE leak was demonstrated in a reachable path (asyncpg's
     message does not echo the password), so this is a redaction-completeness + output-contract defect,
     not a demonstrated secret disclosure — but the named secret-safety control is incomplete.
     Bounded lock-wait/timeouts/plan-mode/CLI-exit-codes are all independently verified working.
```

No Critical finding. The ledger's checksum-mismatch / untracked-schema / partial-applying /
wrong-shaped-ledger / clean-ambiguous-commit / 029-030-boundary behaviors are all correct.

## What was NOT authorized, attempted, or changed

- No migration applied to any shared, test, staging, or production database.
- No implementation file modified (`migration_runner.py`, `run_platform_migrations.py`,
  `migrations/*`, RA-1A + RA-1B suites, and both BE1 allowlist guards are byte-identical to b31e655).
- No feature gate enabled; all four BE3 gates remain default-false.
- No deployment, no worker/relay/consumer activation, no runtime resume/replay, no production approval.
- **PR #21 (Draft/OPEN/unmerged, base=main, head=b31e655) confirmed unchanged before and after and
  NOT merged.** The original review commit 352d546 was preserved unmodified. The reviewer-only
  integration merge (19cff82) exists ONLY on the review branch — NOT FOR MAIN, no PR, no
  source-of-truth claim.
- Gates 1, 2, and 6 are NOT closed by this review.

## Recommendation

```text
Required remediation before RA-1 can PASS / before any shared-apply is authorized:
  - Close M-2 gap A (§13): make plan_chain fail closed (clear diagnostic) when a version is
    ledger-'applied' but its target schema is absent; and either implement a ledger-aware down
    (auditable, lock-protected state transition) OR document that destructive down is not part of the
    ledger-managed apply workflow with application-rollback + table retention as the shared strategy.
  - Close M-2 gap B (§12): record an expected/golden fingerprint per migration and require it to match
    the observed fingerprint at reconcile time, so a wrong-shaped table is rejected as drift.
  - Close M-3: extend redact_for_operator to cover the 'postgresql://' scheme (and other DSN schemes),
    and wrap the CLI's connect step so a connect failure returns the redacted single-JSON result with
    exit code 1/2 instead of a raw traceback.
RA-1 readiness:  H-1 and M-1 CLOSED; M-2 and M-3 not yet. RA-1 migration-runner readiness is NOT yet
                 independently verifiable as complete.
Gates 1/2/6:     remain PENDING — not closed by this review; final status is the PM/PO's call per the
                 canonical gate definition after this closure report.
PR #21:          NOT merge-ready until M-2 (A+B) and M-3 are remediated and re-checked.
Next step:       Product-Owner decision. If remediation is desired, a follow-up implementation stage
                 (the RA-1B implementation session) should close M-2/M-3, after which this reviewer
                 can re-check the two remaining findings. No RA-2 or other stage is started here.
```

## Posture

```text
RA-1FC: FOCUSED CLOSURE COMPLETE | H-1 CLOSED | M-1 CLOSED | M-2 REMEDIATION_REQUIRED | M-3 REMEDIATION_REQUIRED
Overall: RA1_TECHNICAL_VERDICT: REMEDIATION_REQUIRED
Migrations 029-035: unchanged | RA-1B implementation: unchanged | Review commit 352d546: preserved
NOT APPLIED TO SHARED DB | NOT DEPLOYED | NOT ACTIVATED | NOT MERGED
Gates 1/2/6: PENDING (not closed by this review)
production_executed_true_count: 0
```

## Gate wording (reviewer may not self-declare shared migration complete)

```text
RA-1 migration readiness foundation:  PARTIALLY VERIFIED (H-1, M-1 closed; M-2, M-3 open)
Shared DB migration:                  NOT APPLIED
Deployment:                           NOT PERFORMED
Runtime activation:                   NOT PERFORMED
```

---
_Non-production only. No production action. No production data. Neutral labels only — no internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets ("internal test runtime", "isolated ephemeral PostgreSQL 16")._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
