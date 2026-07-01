# Operator Walkthrough Revalidation Notes (Step 64E-R)

> **Staging only — non-production only. No production action. No production secret. No external write.**

Why Step 64E was corrected, and what it means.

## Why Step 64E was corrected
Step 64E was reported as full **PASS**, but the "PASS" reflected only that Claude Code
completed the SOP documents and ran the verifier/tests. The operator correctly noted that this
information **was not confirmed with the operator** — no operator/manager had actually followed
the SOP and validated the walkthrough. Self-running documents and tests is not operator
acceptance.

## What was over-claimed
- Treating `OPERATOR_WALKTHROUGH_SOP_VERIFY: PASS` (document completeness) as if it were
  operator acceptance of the walkthrough.
- Reporting Step 64E as full PASS without an operator validation step.

## What remains valid
- The eight SOP documents exist and are self-consistent (document completeness = PASS).
- The read-only runtime facts they cite are accurate: staging runtime running (22/22),
  `/health` 200, `/operations/safety` 200, demo data present, `production_executed_true_count=0`.
- No production action was taken; the safety posture is unchanged.

## What requires operator confirmation
The operator must complete
[operator-walkthrough-confirmation-form.md](operator-walkthrough-confirmation-form.md): open the
Admin Console via the SSH tunnel and confirm each acceptance item (demo project, work item,
agent executions, audit, metrics, safety posture, understanding of gaps, no public exposure,
integrations disabled), and record whether the SOP is usable.

## What happened next (operator walkthrough completed)
The operator performed the walkthrough live and judged the deployed console **NOT USABLE** —
the demo's per-item evidence (work-item identity, agent executions, workflows, QA/code, audit)
is not visible. Root cause: the orchestrator serves the zero-build static fallback, not the full
React bundle. See [staging-admin-console-deployment-gap.md](staging-admin-console-deployment-gap.md).

## What must happen before Step 64F
- **Remediate** the console deployment gap (build the React bundle into the image, or extend the
  fallback) so the demo evidence is actually visible.
- Operator **re-reviews and accepts** (or explicitly waives).
- Until then, **Step 64F is blocked** and Step 64E overall is `FAILED_OPERATOR_VALIDATION`.

## Process note (to avoid recurrence)
Acceptance items that require a human observation are **operator-owned**; Claude Code marks them
`pending` and must not self-confirm. See the updated
[operator-acceptance-checklist.md](operator-acceptance-checklist.md).

## Safety
No production action; no new workflow executed; no runtime/demo data modified; no gap fixed; no
public exposure; live integrations disabled/mocked; `production_executed_true_count=0`. Claude
Code does not decide production readiness.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
