# Step 66C.4-BE3-RA-1R → Independent Review Result Handoff

> **Independent review result. Records the outcome of the from-scratch technical review of the
> isolated migration rehearsal (RA-1A) and its new migration-runner safeguard. Authorizes NO shared
> migration application, NO deployment, NO feature-gate change, NO activation, NO merge. Migrations
> 031-035 and `migration_runner.py` were NOT modified by this review. Gates 1/2/6 remain PENDING —
> this review does NOT close them.**

## Result

```text
Process marker:        STEP66C4_BE3_RA1_INDEPENDENT_REVIEW_VERIFY: PASS
Technical verdict:     RA1_TECHNICAL_VERDICT: REMEDIATION_REQUIRED
```

An independent reviewer (not the RA-1A implementation session) re-derived every RA-1A claim from
the committed migration SQL, `migration_runner.py`, and direct experiments against an isolated
ephemeral PostgreSQL 16, and additionally exercised the `apply_chain_locked` FAILURE path that
RA-1A's own suite never touches. The isolated rehearsal RA-1A executed is correct and its claims
reproduce (its 12 tests re-run 12 passed; this review's own 14 tests 14 passed, 0 skipped). The
`REMEDIATION_REQUIRED` verdict is scoped to the **future shared-apply readiness foundation** (the new
`migration_runner.py`), not to the rehearsal's own executed scope, and not to migrations 031-035
(which have no blocking defect).

## Findings (full detail in be3-ra1-independent-migration-review.md)

```text
H-1 (High, blocks shared-apply):  apply_chain_locked issues no ROLLBACK on failure; its finally-block
                                  pg_advisory_unlock runs on an aborted connection, itself fails,
                                  masks the real migration error, and does not release the lock
                                  (lock freed only by connection teardown). Docstring's "lock is
                                  released even if a migration fails" is not honored by the code.
M-1 (Medium, blocks shared-apply):schema_fingerprint does not capture FK referential actions
                                  (ON DELETE/UPDATE), CHECK expression bodies, or deferrability —
                                  a same-named semantic change is invisible.
M-2 (Medium, blocks shared-apply):no migration ledger / no version provenance; "applied" is
                                  existence-only introspection — cannot tell which version created a
                                  table, nor detect a manually-altered column by existence alone.
M-3 (Medium, blocks shared-apply):no bounded lock-wait / statement timeout; a hung holder blocks
                                  waiters forever; no dry-run/plan/current-state/audit model.
L-1 (Low):                        down-script CASCADE asymmetry (031 down no CASCADE; 032-035 CASCADE)
                                  — safe in reverse order, latent foot-gun if mis-ordered.
L-2 (Low/clarification):          "no partial schema" = no half-built object, not chain atomicity
                                  (each file self-COMMITs); recovery is idempotent reapply.
```

No Critical finding. Migrations 031-035, existing-data preservation, the pre-activation-down
boundary (correctly documented, never overclaimed), the post-write non-destructive rollback, and
old-version compatibility all passed independently.

## What was NOT authorized, attempted, or changed

- No migration applied to any shared, test, staging, or production database.
- No file under review modified (`migration_runner.py`, `migrations/*`, RA-1A test suite unchanged).
- No feature gate enabled; all four BE3 gates remain default-false.
- No deployment, no worker/relay/consumer activation, no runtime resume/replay, no production approval.
- **PR #21 (Draft/OPEN/unmerged, base=main, head=27184b5) was confirmed unchanged before and after
  this review and was NOT merged.** No branch (`review/66c4-be3-ra1-migration-rollback`,
  `feature/66c4-be3-ra1-migration-rehearsal`) was merged.
- Gates 1, 2, and 6 in `be3-runtime-activation-gate.md` are NOT closed by this review.

## Recommendation

```text
Required remediation before any shared-apply is authorized:
  - Close H-1: explicit ROLLBACK on failure before unlock; re-raise the ORIGINAL error; guarantee
    the advisory lock is released on every exception path (not only via connection teardown).
  - Close M-1: extend schema_fingerprint to capture FK referential actions, CHECK expressions, and
    constraint deferrability (e.g. via pg_constraint / information_schema.referential_constraints).
  - Close M-2: add a migration ledger or a stored per-migration golden fingerprint + shape-match
    check so provenance and drift are decidable.
  - Close M-3: add bounded lock_timeout + statement_timeout and an operator-facing
    dry-run/plan/current-state/audit path.
Gates 1/2/6:  remain PENDING (not closed). This review does not authorize closing them.
PR #21:       NOT merge-ready as a shared-apply foundation until H-1 and M-1..M-3 are remediated and
              re-reviewed. (It remains a valid Draft rehearsal artifact; merge is the PO's decision.)
Next step:    Product-Owner decision. If remediation is desired, a follow-up implementation stage
              should address H-1/M-1/M-2/M-3, after which a re-review can re-evaluate the verdict.
              No RA-2 or other stage is started by this review.
```

## Posture

```text
RA-1R: INDEPENDENT REVIEW COMPLETE | VERDICT: REMEDIATION_REQUIRED (shared-apply foundation)
Isolated rehearsal (RA-1A executed scope): CORRECT / RE-DERIVED
Migrations 031-035: no blocking defect | Existing data: fully preserved
NOT APPLIED TO SHARED DB | NOT DEPLOYED | NOT ACTIVATED | NOT MERGED
Gates 1/2/6: PENDING (not closed by this review)
production_executed_true_count: 0
```

---
_Non-production only. No production action. No production data. Neutral labels only — no internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets ("internal test runtime", "isolated ephemeral PostgreSQL 16")._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
