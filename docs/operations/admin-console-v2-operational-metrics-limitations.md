# Admin Console v2 — Operational Metrics Limitations (Step 58)

Step 58 is **operational visibility**, not a production operations center.

## What it is
A read-only aggregation of existing platform state (delivery / work items / dispatch /
agents / workflows / runtime smoke / ArgoCD manual sync / security readiness / approval /
audit / safety) into metrics + an Admin Console v2 dashboard.

## Limitations (honest)
- **Visibility only** — metrics are NOT production readiness, NOT an SLA/SLO guarantee,
  NOT a release gate. Delivery completed ≠ production approved; security baseline PASS ≠
  all-risks-remediated.
- **Freshness** — runtime / GitOps metrics come from the Step 55 / 56 evidence reports;
  when a report is absent or the kind cluster / ArgoCD is down, the metric is shown
  **stale / unavailable**, never faked. Step 58 never re-runs the smoke or triggers a sync.
- **Security metrics** are modeled / not-production-enforced (Step 54 posture).
- **Delivery metrics** reflect the Step 57 non-production multi-project baseline (not
  multi-tenant).
- **Admin Console** is read-only here — no deploy / sync / PR / external send / production
  approve / production-ready / connector control.
- **Not multi-tenant** — see the tenant strategy note; Step 58 does not implement tenant
  isolation or connectors.

## Out of scope / next
- **Step 59** — Sandbox GitHub Draft PR Flow.

No ArgoCD sync, no Kubernetes mutation, no GitHub write, no external send, no production
action; `production_executed_true_count=0`. **Claude Code does not decide production
readiness.**
