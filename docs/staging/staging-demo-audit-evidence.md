# Staging Demo Audit Evidence (Step 64D)

> **Staging only — non-production only. No production action. No production secret. No external write.**

Audit evidence produced by the Step 64D demo on the staging runtime (`10.0.1.32`).

## Work-item audit event
`GET /operations/delivery/work-items/386a3f95-…/events` →

| Field | Value |
|---|---|
| event_type | `work_item_created` |
| from_state → to_state | `null` → `created` |
| actor | `staging-demo` |
| role | `intake` |
| reason | `staging demo seed` |
| correlation_id | the work item id |
| work_item | `WI-0001` (Create user CRUD API) |

The event carries governed audit metadata (`build_audit_metadata`) — same shape as the
communication-gateway mock intake.

## Workflow audit references
Each mock-workflow run recorded an audit reference:
- `demo-crud-userapi` → workflow `wf-70de1623af5b`, `audit_refs=[5a8943c3-…]`.
- `demo-crud-001` → workflow `wf-0f6e671d3669`, `audit_refs=[2fac517e-…]`.

## Audit totals
`GET /operations/summary → audit_summary` → `audit_logs_total = 60`,
`audit_logs_recent_24h = 60`. The demo drove the audit log growth (fresh staging DB started at
0 before Step 64D).

## Integrity / safety
- All audit events are non-production: `production_executed=false`, no external write, no
  production secret.
- No audit tampering; audit canonicalization unchanged; `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false live-integrations=disabled demo-workflow-executed=true -->
