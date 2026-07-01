# Admin Console Demo Evidence Endpoint Map (Step 64E.3A)

> **Staging only — non-production only. No production action. No production secret. No external write.**

Backend endpoints relevant to the five demo-evidence items, probed read-only (GET) against
`http://127.0.0.1:18000` on `10.0.1.32`. "Frontend consumer" = whether the deployed Admin Console
calls it (from source inspection).

| Endpoint | Method | Status | Data type | Contains demo evidence | Response shape (summary) | Frontend consumer |
|---|---|---|---|---|---|---|
| `/operations/admin-console/projects` | GET | 200 | project summaries | project yes / **work items no** | `projects[]` with pilot/package/readiness rollups, **no `work_items`** | Projects page |
| `/operations/admin-console/projects/{id}` | GET | 200 | project detail | project yes / **work items no** | `{project, rollup, latest_pilot, latest_delivery_package}` — **no `work_items`** | ProjectDetail (rows not linked) |
| `/operations/admin-console/latest-delivery-state` | GET | 200 | pilot/delivery rollup | **no** (`latest_pilot=None`) | `{latest_pilot:null, latest_delivery_package, acceptance_gate, …}` | WorkspaceExecution, TaskGraph |
| `/operations/delivery/projects` | GET | 200 | delivery projects | project yes | `projects[]` (key/name/env/production) | Multi-project Delivery |
| `/operations/delivery/projects/{id}/work-items` | GET | 200 | work items | **WI-0001 yes** | `work_items[]` (id/key/title/lifecycle/production_effect) | Multi-project Delivery (**on project select only**) |
| `/operations/delivery/work-items/{id}/events` | GET | 200 | audit events | **work_item_created yes** | `events[]` (event_type/from→to/actor/metadata) | **none** |
| `/operations/qa/runs` | GET | 200 | QA runs | **yes (2)** | `{count, runs[]}` | **none** |
| `/operations/code/workspaces` | GET | 200 | code workspaces | **yes (2)** | `{count, workspaces[]}` | **none** |
| `/operations/metrics/agents` | GET | 200 | aggregate | counts only | `agent_execution_count_total/_by_agent/_by_status` | Operational Metrics |
| `/operations/metrics/workflows` | GET | 200 | aggregate | counts only | workflow totals | Operational Metrics |
| `/operations/metrics/audit` | GET | 200 | aggregate | count only | audit log totals | Operational Metrics |
| `/workflow` (app-level, not `/operations`) | GET | 200 | per-workflow list | yes | `{count, workflows[]}` | **none** (UI calls only `/operations/*`) |

## Key gaps
- Per-item demo data lives in `/operations/delivery/*` (work items + events), `/operations/qa/*`,
  `/operations/code/*` — **none of which the deployed UI consumes** except delivery projects (and
  work-items only on manual select).
- The pages that *look* relevant (WorkspaceExecution/TaskGraph/Projects) read the **admin-console
  pilot/rollup** endpoints, which are empty for the demo (`latest_pilot=None`, no `work_items`).

## Status
Read-only; no code change; no rebuild/restart; `production_executed_true_count=0`. Step 64E
FAILED_OPERATOR_VALIDATION; Step 64F BLOCKED.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
