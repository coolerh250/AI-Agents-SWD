# Admin Console v2 — Operational Metrics Dashboard (Step 58)

- Page: `apps/admin-console/src/pages/OperationalMetrics.tsx` (route `/metrics`) + static fallback
- Verifier: `scripts/verify_admin_console_v2_operational_metrics.py` → `ADMIN_CONSOLE_V2_OPERATIONAL_METRICS_VERIFY`

A **read-only** operational metrics dashboard with sections for overview, delivery,
project / work item, dispatch, agent execution, workflow, runtime smoke, ArgoCD manual
sync, security readiness, approval, audit, safety posture, and freshness / stale data.

UI safety: there is **no** deploy / ArgoCD sync / GitHub PR / external send / production
approve / production-ready / connector control. Unavailable or stale sources are shown
explicitly (`available: false` + reason). All production-readiness indicators render
false. The dashboard links to existing project / work-item views without changing their
mutation scope. Metrics are visibility only — not production readiness, not an SLA/SLO.

> Step 59 adds a separate read-only **Sandbox GitHub Draft PR** section (route
> `/sandbox-github`); see [sandbox-github-draft-pr-runtime.md](sandbox-github-draft-pr-runtime.md).
> It is a sandbox-only draft-PR flow, not a metrics view, and carries no merge / workflow /
> production / token control.
