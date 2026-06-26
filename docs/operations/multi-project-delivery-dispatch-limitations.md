# Multi-project Delivery & Work-item Dispatch — Limitations (Step 57)

Step 57 delivers a **multi-project delivery and work-item dispatch baseline**. It is
**NOT** fully autonomous project management, production delivery automation, or
multi-tenant production ready.

## What is real
Multiple projects with a registry, project-scoped work items with a delivery lifecycle,
deterministic dispatch to internal agents with correlation tracking, project
delivery-state rollup, delivery-package linkage, project-scoped audit, and an Admin
Console view with audited create/dispatch.

## Limitations (honest)
- **Deterministic dispatch only** — no LLM decomposition; dispatch routes to internal
  agent streams, not real execution orchestration of every agent.
- **No external integration** — no GitHub write / PR, no Jira/Linear/Issues, no
  Slack/email/webhook send (mock notification events only).
- **No production path** — no production deploy, no ArgoCD sync/auto-sync, no production
  release gate, no multi-tenant production isolation, no billing.
- **production_effect work items are not executed** — they route to waiting_approval;
  human acceptance ≠ deployment approval; delivery-package-ready ≠ production approval.
- **Agent assignment** is capability/role based with a blocked fallback; manual
  reassignment is future work.

## Out of scope / next
- Step 58 — Admin Console v2 Operational Metrics.
- Step 59 — Sandbox GitHub Draft PR Flow.

No GitHub write / image push / registry login / ArgoCD sync / external send / production
action; `production_executed_true_count=0`. Claude Code does not decide production
readiness.
