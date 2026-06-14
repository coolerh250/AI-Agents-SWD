# Project Planner Agent (Stage 45)

The project-planner-agent turns a software *request* into a **project plan**
(brief + user stories + acceptance criteria + milestones + a validated work-item
task graph). It is the foundation that moves the platform from a linear
`intake → requirement → development → QA → devops` pipeline toward a
project-delivery platform.

It is **planning-only**. It does not write a repo, open a PR, deploy, call a real
LLM, or dispatch work to the development-agent. `production_executed` is always
`false`.

## Purpose

* Accept a user software request.
* Produce a deterministic project brief (scope / non-scope / assumptions /
  constraints / success metrics).
* Produce user stories, acceptance criteria, milestones.
* Build a work-item task graph with dependencies and suggested agent roles.
* Validate the dependency graph (cycle / self / duplicate / missing node).
* Persist everything and let the orchestrator track project status.

## Planner input

| Field | Notes |
|---|---|
| `task_id` | source task (optional) |
| `request_text` | the raw request (required) |
| `requirement_summary` | optional requirement-agent summary |
| `source` | `operator` / `orchestrator` |
| `requester` | optional |
| `project_type` | optional override; otherwise detected from the template |
| `autonomy_level` | default `autonomous_dev_test` |
| `dispatch_policy` | default `planning_only` |

## Planner output

`project_id`, `brief_id`, `graph_snapshot_id`, `work_items_count`,
`dependencies_count`, `acceptance_criteria_count`, `risks_count`,
`milestones_count`, `user_stories_count`, `validation_status`,
`requires_clarification`, `planning_only=true`, `production_executed=false`,
`status`, `template`.

If `requires_clarification=true` the planner creates the project in `draft`
status with a `clarification_needed` artifact and **no executable work items**.

## Two entry points

1. **Synchronous** — `POST /operations/projects/plan` (used by the verify
   script and operators). Runs the planner inline and returns the
   `PlannerOutput`.
2. **Stream** — the agent consumes `stream.project_planning`
   (`requirement.project_planning_requested` events emitted by the
   requirement-agent for project-scale request types), plans, and reports
   `project.planning_completed` on `stream.project_events`. The orchestrator
   then sets the workflow stage to `project_planned` (planning-only — it does
   **not** advance to development).

## FastAPI Todo template

The first shipped template (`fastapi_todo_service`) is triggered by requests
like "Create a FastAPI Todo Service", "建立 FastAPI Todo CRUD",
"FastAPI + SQLite + pytest + README". It produces ≥7 milestones, ≥8 work items
(REQ/ARCH/BE/DB/QA/DOC/DEL), ≥5 dependencies, ≥8 acceptance criteria, and a risk
register. See [project-task-graph.md](project-task-graph.md).

## Graph validation

`shared/sdk/project_planning/dependency_validator.py` rejects self-dependencies,
duplicate dependencies, dependencies that reference a missing node, and cycles.
Isolated nodes downgrade the status to `warning`. An `invalid` graph sets the
workflow stage to `planning_failed` and is **not** dispatched.

## Limitations / safety constraints

* No real LLM (`ENABLE_PROJECT_PLANNER_REAL_LLM=false`, template mode).
* No work-item dispatch (`ENABLE_PROJECT_WORK_ITEM_DISPATCH=false`).
* No GitHub write, no deployment, no production execution.
* `project.*` notification events are on the default real-delivery denylist.
* Audit rows carry only project decisions / artifact refs / summaries — never
  chain-of-thought, never secrets.
* Future agent roles (planner-agent, architecture-capability,
  security-capability, delivery-capability) are *suggestions* — they never cause
  a dispatch failure and stay `planning_only`.
