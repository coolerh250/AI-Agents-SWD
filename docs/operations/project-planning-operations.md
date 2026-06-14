# Project Planning Operations (Stage 45)

Read-only project visibility plus one planning-only write endpoint, all under
`/operations/*` on the orchestrator (port 8000).

## Endpoints

### Plan (write — planning-only)
* `POST /operations/projects/plan` — body `{ "request_text": "..." }`. Runs the
  deterministic template planner, persists the project graph, returns the
  `PlannerOutput`. Never calls an LLM, writes GitHub, or deploys.

### Project reads
* `GET /operations/projects` (`?status=`)
* `GET /operations/projects/{id}`
* `GET /operations/projects/{id}/brief`
* `GET /operations/projects/{id}/stories`
* `GET /operations/projects/{id}/acceptance-criteria`
* `GET /operations/projects/{id}/milestones`
* `GET /operations/projects/{id}/work-items` (`?status=`)
* `GET /operations/projects/{id}/dependencies`
* `GET /operations/projects/{id}/risks`
* `GET /operations/projects/{id}/graph`
* `GET /operations/projects/{id}/progress`
* `GET /operations/projects/{id}/delivery-readiness`

### Work-item reads / status
* `GET /operations/project-work-items?project_id=...`
* `GET /operations/project-work-items/{id}`
* `POST /operations/project-work-items/{id}/status` — body `{ "status": "..." }`
* `GET /operations/project-work-items/{id}/dependencies`
* `GET /operations/project-work-items/{id}/acceptance-criteria`

## Safety surface (`GET /operations/safety`)

New fields:

* `project_planner_enabled`
* `project_planner_planning_only` (expected `true`)
* `project_task_graph_enabled` (`true`)
* `project_work_item_dispatch_enabled` (expected `false`)
* `project_planner_real_llm_enabled` (expected `false`)
* `project_planner_production_execution_enabled` (`false`)
* `latest_project_planning_status`
* `latest_project_id`
* `latest_project_graph_validation_status`
* `project_delivery_pilot_ready` (`false` this stage)

## Verify

`scripts/verify_project_planner_task_graph.sh` exercises service health, a
FastAPI Todo plan, planning-only safety, the operations API, audit/notification
denylisting, and full-regression compatibility. Marker:
`PROJECT_PLANNER_TASK_GRAPH_VERIFY: PASS`.

Runtime smokes 153–164 in `check_runtime_state.sh` cover the same surfaces.

## Safety notes

* All read endpoints are side-effect free.
* No response carries a secret or chain-of-thought; only briefs / graphs /
  summaries.
* `project.*` notification events are blocked from real Discord delivery by the
  default denylist.
