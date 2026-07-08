# Staging Functional Acceptance — Operator Decision Template (Step 65I)

> **Staging only — non-production only. No production action. No production data.**
> **Claude Code does not decide staging functional acceptance. Only the operator records the verdict below.**

The operator records exactly **one** verdict for the whole Step 65 staging functional validation
track. This decision is about **staging functional acceptance only** — it is **not** production
readiness and **not** a production-deployment authorization.

## Decision options
```
Step 65 — Staging Functional Acceptance — operator verdict (choose ONE)

[ ] PASS
    All required staging functional validation passed and the documented gaps are not material.

[ ] PASS_WITH_ACCEPTED_GAPS   (Claude Code's non-binding recommendation)
    Staging functional validation is accepted as sufficient, while acknowledging the documented gaps
    (see the gap register). The gaps enter backlog / pre-production planning. This does NOT authorize
    production.

[ ] FAIL
    One or more gaps block staging functional validation. (Name which gap(s): ____________________)

Operator: ____________________    Date: ____________________
Notes / accepted gaps: __________________________________________
```

## What each verdict means (next actions in
[staging-functional-acceptance-next-actions.md](staging-functional-acceptance-next-actions.md))
- **PASS** → Step 65 track closes as fully accepted; gaps (if any) still recorded.
- **PASS_WITH_ACCEPTED_GAPS** → Step 65 track closes as accepted-with-gaps; the accepted gaps and
  production-readiness items move to backlog / pre-production planning.
- **FAIL** → the named blocking gap(s) are re-opened; Claude Code addresses them under a new
  authorization before re-requesting acceptance.

## Standing constraints (independent of the verdict)
- No verdict here authorizes production deployment, production sync, production secrets, or closes
  production rollout gaps. Production readiness is a **separate** decision — see
  [staging-functional-acceptance-production-readiness-separation.md](staging-functional-acceptance-production-readiness-separation.md).
- `production_executed_true_count=0` throughout Step 65.

## Status
Operator verdict: **PENDING**. `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production data._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
