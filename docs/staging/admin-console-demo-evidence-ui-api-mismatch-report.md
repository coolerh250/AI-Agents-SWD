# Admin Console Demo Evidence UI/API Mismatch Report (Step 64E.3A)

> **Staging only — non-production only. No production action. No production secret. No external write.**

Root-cause category (from the fixed list) for each of the five failed items.

| # | Item | Root cause category | One-line |
|---|---|---|---|
| 1 | WI-0001 | **route exists but renders summary only** + **UI lacks default project/work-item display (selection required)** | work items load only after a manual project select in Multi-project Delivery; Projects/ProjectDetail carry no `work_items` |
| 2 | Agent executions | **UI calls wrong endpoint / no per-execution view** (reads `latest_pilot`, which is empty) | the only "workspace" page reads the delivery-pilot model the demo didn't populate; no per-execution list is consumed |
| 3 | Workflow | **route exists but renders summary only / stub** | only `/operations/metrics/workflows` aggregate is shown; TaskGraph is a planned stub; no per-workflow list |
| 4 | QA / code output | **endpoint returns data but UI does not call it** | `/operations/qa/runs` + `/operations/code/workspaces` return demo data but no frontend page calls them |
| 5 | Audit / evidence | **UI shows aggregate only; per-event data not consumed** | only `/operations/metrics/audit` count is shown; `/operations/delivery/work-items/{id}/events` is not consumed |

## Primary vs secondary
- **Primary blocker:** the Admin Console v0 pages target a **delivery-pilot + aggregate-metrics**
  data model, while the demo populated the **mock-workflow + seeded work-item** path. The per-item
  demo records exist in the backend but are not the records the pages read.
- **Secondary blockers:** (a) QA/code endpoints entirely unwired in the UI; (b) work items gated
  behind manual selection; (c) TaskGraph/per-item drill-down not implemented; (d) no per-execution
  or per-event audit list views exist.

## Not a bundle problem anymore
The Step 64E.1 remediation correctly deployed the full React bundle (all routes present); this
report confirms the remaining blocker is **UI/API data-model integration**, not deployment.

## Status
Read-only diagnosis; no remediation implemented; `production_executed_true_count=0`. Step 64E
FAILED_OPERATOR_VALIDATION; Step 64F BLOCKED.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
