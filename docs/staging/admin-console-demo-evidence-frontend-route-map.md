# Admin Console Demo Evidence Frontend Route Map (Step 64E.3A)

> **Staging only — non-production only. No production action. No production secret. No external write.**

Frontend routes/components relevant to the five demo-evidence items (from
`apps/admin-console/src`, read-only). `API_BASE` defaults to `""` → relative same-origin paths.

| Route | Component | Nav entry | API dependency | Expected data shape | Current visible behavior | Gap |
|---|---|---|---|---|---|---|
| `/projects` | `Projects` | yes | `/operations/admin-console/projects` | `projects[]` (rollups) | shows the demo project row; **rows not clickable** | no `work_items`; no link to detail |
| `/projects/:id` | `ProjectDetail` | (no direct link) | `/operations/admin-console/projects/{id}` | `{project, rollup, latest_pilot, latest_delivery_package}` | not reachable from the list | no `work_items` in response; unlinked |
| `/delivery` | `MultiProjectDelivery` | yes | `/operations/delivery/projects` + `…/{id}/work-items` on **select** | `projects[]`, `work_items[]` | lists projects; work items only after selecting a project | selection required; work items not shown by default |
| `/workspace` | `WorkspaceExecution` | yes* | `/operations/admin-console/latest-delivery-state` → `latest_pilot` | pilot summary | **EmptyState** ("No workspace execution available yet") — `latest_pilot=None` | reads pilot model the demo didn't populate; not agent executions |
| `/task-graph` | `TaskGraph` | yes* | latest pilot context | pilot context | **stub** ("drill-down is planned") + EmptyState | not implemented; no per-workflow/work-item graph |
| `/operator` | `OperatorConsole` | yes* | operator-action reads (gated) | package id inputs | operator-action console (gated) | not an executions/audit view |
| `/metrics` | `OperationalMetrics` | yes | `/operations/metrics/*` (agents/workflows/audit/…) | aggregate counts | shows projects=1, work items=1, counts | **aggregate only**, no per-item detail |
| `/safety` | `SafetyCenter` | yes | `/operations/safety` (summary) | safety fields | shows safety posture (correct) | n/a (this works) |

\* Nav entries `Workspace Execution`, `Task Graph`, `Operator Console`, `Design Review`, `Mini
Delivery Pilot` exist in the React `Nav.tsx` (now deployed after Step 64E.1) but render
pilot/stub/empty content for this demo.

## Missing per-item views (not present in the frontend at all)
- **Agent executions** list · **Workflows** list · **QA runs** view · **Code workspaces** view ·
  **Per-event audit** view. None of these pages/getters exist; the QA/code endpoints are not
  called anywhere.

## Status
Read-only; no code change; `production_executed_true_count=0`. Step 64E FAILED_OPERATOR_VALIDATION;
Step 64F BLOCKED.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
