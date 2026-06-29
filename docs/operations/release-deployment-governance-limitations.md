# Release Governance — Limitations (Step 60)

This is a **non-production release & deployment governance baseline**. It must NOT be
described as:

- production deployment ready
- production release approved
- automatic production promotion ready
- production GitOps ready

## What it does
- Aggregates delivery / work-item / sandbox-draft-PR / runtime / GitOps / security /
  approval evidence into a **non-production** release candidate, deployment intent (intent
  only), evidence package, and readiness decision — with audit and full linkage.

## What it deliberately does NOT do
- No production deploy, no production ArgoCD sync, no production Kubernetes mutation.
- No PR merge, no ready-for-review, no GitHub workflow dispatch, no image push, no
  registry login, no GitHub release/tag creation.
- No production target accepted (rejected by policy + DB CHECK), no auto-promotion.
- A deployment intent never executes a deployment.
- No external notification send, no BYOR connector, no tenant isolation runtime.

## Governance ≠ approval
- A release candidate marked `accepted_nonproduction` is **not** a production approval.
- A delivery-package-ready is not a production approval; a security baseline PASS is not a
  production approval; a sandbox draft PR is not a merge/review approval.
- A human-review request is **not** a human approval.

## Observations / next phase
- `release_governance_production_ready=false`, `production_executed_true_count=0`.
- Recommended next phase: **Step 61 — Production Backup/Restore/DR Operations or a
  controlled cleanup review** (operator decision).
- Claude Code must not decide Production readiness.
