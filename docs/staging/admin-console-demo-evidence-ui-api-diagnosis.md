# Admin Console Demo Evidence UI/API Diagnosis (Step 64E.3A)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Read-only diagnosis. No code change, no rebuild, no restart, no data mutation.**

Root-cause diagnosis for the five demo-evidence items the operator could not see in the deployed
Admin Console, after the Step 64E.1 React bundle was deployed. Evidence is from read-only source
inspection + GET probes against `http://127.0.0.1:18000` on `10.0.1.32`.

## Overarching root cause
The Admin Console v0 pages are built around a **delivery-pilot + aggregate-metrics** data model
(`latest_pilot`, `latest_delivery_package`, `acceptance_gate`, `/operations/metrics/*` counts).
The Step 64D demo exercised the **mock-workflow + seeded delivery work-item** path, which
populates a *different* set of records (agent-execution store, workflow store, a delivery work
item at lifecycle `created`, QA runs, code workspaces). The pages therefore (a) read a model the
demo didn't populate (`latest_pilot=None`), (b) show only aggregate counts, (c) are unwired to
the QA/code endpoints, (d) are stubs, or (e) gate the data behind a manual project selection. The
data exists; the per-item UI surfaces do not present it.

## 1. WI-0001 (work item identity) — diagnosis
- **Backend data status:** EXISTS. `GET /operations/delivery/projects/{id}/work-items` returns
  `WI-0001` "Create user CRUD API" (`production_effect=false`).
- **API route status:** reachable (200).
- **Frontend route status:** `MultiProjectDelivery` (`/delivery`) *does* call
  `getDeliveryWorkItems(pid)` — **but only after a project is selected** (`selected` state). The
  `Projects` (`/projects`) + `ProjectDetail` (`/projects/:id`) pages use
  `/operations/admin-console/projects[/{id}]`, whose responses contain **no `work_items`** (only
  pilot/package/readiness rollups). Projects rows are not linked to the detail route.
- **UI/API mismatch:** *route exists but renders summary only + project-selection required.* The
  only path to WI-0001 is Multi-project Delivery → manually select the project (operator didn't);
  Projects/ProjectDetail never expose work items.
- **Operator impact:** work item invisible unless the operator selects the project.
- **Recommended fix:** auto-select the first project (or default-load its work items) in
  Multi-project Delivery; show a visible work-items table; optionally include `work_items` in the
  admin-console project detail.

## 2. Agent executions — diagnosis
- **Backend data status:** EXISTS. Aggregate at `GET /operations/metrics/agents`
  (`agent_execution_count_total`, `_by_agent`, `_by_status`); per-execution rows in the
  agent-execution store (gateway `:18004/executions`).
- **API route status:** aggregate reachable (200); **no per-execution list under
  `/operations/*` on `:18000`** is consumed by the UI.
- **Frontend route status:** `WorkspaceExecution` (`/workspace`) reads
  `getLatestDeliveryState().latest_pilot`, which is **`None`** for the demo (no delivery pilot
  was run). No page lists agent executions.
- **UI/API mismatch:** *UI has no per-execution view; the pages that exist read the delivery-pilot
  model the demo didn't populate; only aggregate metrics available.*
- **Operator impact:** the completed intake→…→devops pipeline is invisible.
- **Recommended fix:** add a per-execution list view backed by a read-only `/operations`
  executions endpoint (or surface `metrics/agents` counts + a list), **or** exercise the demo
  through the delivery-pilot path so `latest_pilot` populates.

## 3. Workflow — diagnosis
- **Backend data status:** EXISTS. Aggregate at `GET /operations/metrics/workflows`; per-workflow
  list at app-level `GET /workflow` (not under `/operations`, not called by the UI).
- **API route status:** aggregate reachable; per-workflow list not exposed under `/operations`.
- **Frontend route status:** only `/operations/metrics/workflows` (aggregate) is consumed;
  `TaskGraph` (`/task-graph`) is a **stub** ("Per-project work-item graph drill-down is planned").
- **UI/API mismatch:** *route exists but renders summary/stub only; no per-workflow list.*
- **Operator impact:** the 2 completed workflows are shown only as counts.
- **Recommended fix:** add a workflows list view backed by a read-only `/operations` workflows
  endpoint (or expose `/workflow` read-only under `/operations`).

## 4. QA / code output — diagnosis
- **Backend data status:** EXISTS. `GET /operations/qa/runs` (200, 2 runs) + `GET
  /operations/code/workspaces` (200, 2 workspaces).
- **API route status:** reachable (200).
- **Frontend route status:** **no frontend page calls `/operations/qa/*` or
  `/operations/code/*`** (confirmed by source grep). `WorkspaceExecution` calls
  latest-delivery-state instead.
- **UI/API mismatch:** *endpoints return data but the UI does not call them.*
- **Operator impact:** QA runs + code workspaces invisible.
- **Recommended fix:** add API getters + a QA/Code page (or wire an existing page) to call
  `/operations/qa/runs` + `/operations/code/workspaces`.

## 5. Audit / evidence — diagnosis
- **Backend data status:** EXISTS (per-item). Work-item audit event at
  `GET /operations/delivery/work-items/{id}/events` (`work_item_created`); aggregate total at
  `GET /operations/metrics/audit`. (The `/operations/.../audit*` integrity/forensics endpoints are
  a different, model/integrity surface.)
- **API route status:** per-event (delivery events) + aggregate reachable.
- **Frontend route status:** only `/operations/metrics/audit` (aggregate count) is consumed; no
  per-event audit view for the demo work item.
- **UI/API mismatch:** *UI shows aggregate audit count only; no per-event audit view wired to the
  demo's work-item events.*
- **Operator impact:** audit evidence shown only as a total count.
- **Recommended fix:** add an audit-events view calling
  `/operations/delivery/work-items/{id}/events` (or a per-event audit endpoint).

## Status
- **Step 64E:** FAILED_OPERATOR_VALIDATION. **Step 64F:** BLOCKED. No remediation implemented.
- Read-only diagnosis only; no rebuild, restart, or data change; `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
