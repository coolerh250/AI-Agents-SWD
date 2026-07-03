# Staging Functional Acceptance Criteria (Step 65A)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Criteria / documentation only. Claude Code does not decide staging functional acceptance.**

Defines the verdict criteria for staging functional acceptance (the Step 65I outcome). The operator
gives the verdict; Claude Code records it.

## PASS
- A fresh **end-to-end workflow from intake** runs and its evidence is visible on the **formal**
  Admin Console pages (65G).
- The in-scope **controlled external integrations** (GitHub / notification / LLM, as scoped by the
  operator) are validated against sandbox/non-production resources (65D–65F).
- **Failure / recovery / governance** paths (approval, cancel/abort, retry/DLQ) are exercised in
  staging (65H).
- Safety preserved throughout: `production_executed_true_count=0`; no production action; no external
  write beyond authorized sandbox targets.
- Operator gives an explicit PASS verdict at 65I.

## PASS_WITH_ACCEPTED_GAPS
- All required core paths validated, but specific gaps remain that the operator **explicitly
  accepts** (e.g. SPA deep-link 404; an integration the operator deferred; a scenario deferred to a
  later phase).
- Each accepted gap is documented and does not hide a required capability.

## FAIL
- A required capability is missing or only visible via mock/seeded/diagnostic evidence when a real
  staging validation was required.
- Any safety violation (`production_executed_true_count>0`, unauthorized external write, production
  action).
- Operator withholds acceptance.

## Notes
- "All functions" for acceptance = the domains in
  [staging-functional-coverage-matrix.md](staging-functional-coverage-matrix.md), scoped by the
  operator; the operator confirms the scope after 65A.
- Production readiness is **not** part of these criteria and is not decided by Claude Code.
- Diagnostics / Demo Evidence is never an acceptance path.

## Posture
Documentation only. No runtime change, no workflow execution, no integration enablement, no secret
creation, no production action; `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
