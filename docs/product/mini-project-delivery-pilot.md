# Mini Project Delivery Pilot (Stage 48)

## Purpose

The first verifiable, end-to-end **controlled** delivery path. One pilot run
chains the three preceding stages into a single governed flow and produces
evidence at every step. It is **not** production delivery, **not** a real
GitHub PR, **not** a deploy.

```
User Request
  → Project Planner (Stage 45)
  → Task Graph
  → Design Review (Stage 46)
  → Controlled Workspace Execution (Stage 47)
  → Test / Static Check Evidence
  → Acceptance Criteria Evaluation (evidence-based)
  → QA Summary
  → Safety Summary
  → Mini Delivery Pilot Report
```

## Pilot execution path

The pilot runner records a `mini_delivery_pilot_steps` row per stage
(`project_plan`, `design_review`, `workspace_execution`, `test_execution`,
`acceptance_evaluation`, `qa_summary`, `safety_summary`, `pilot_report`). A
failing required step sets the pilot `failed`/`blocked` — failures are never
swallowed.

## Input / output

Input (`MiniDeliveryPilotRequest`): `request_text`, optional `project_id` /
`design_review_session_id` / `workspace_id`, `pilot_type`
(`fastapi_todo_service`), `controlled_only=true`.

Output (`MiniDeliveryPilotResult`): `pilot_id`, `project_id`,
`design_review_session_id`, `workspace_id`, `qa_report_id`,
`safety_report_id`, `mini_delivery_report_id`, acceptance counts
(`total`/`satisfied`/`failed`/`pending`), `qa_status`, `safety_status`,
`pilot_status`, and the controlled-only flags (`production_executed=false`,
`github_write_performed=false`, `pr_created=false`,
`deployment_performed=false`, `real_llm_used=false`).

## Controlled-only mode

`MINI_DELIVERY_PILOT_CONTROLLED_ONLY=true`,
`ENABLE_MINI_DELIVERY_REAL_LLM=false`,
`ENABLE_MINI_DELIVERY_GITHUB_WRITE=false`,
`ENABLE_MINI_DELIVERY_PR_CREATION=false`,
`ENABLE_MINI_DELIVERY_DEPLOY=false`,
`ENABLE_MINI_DELIVERY_EXTERNAL_DELIVERY=false`.

## Integrations (reuse, not re-implement)

* **Project planner** — `plan_project` (Stage 45). If no `project_id` is given
  the pilot plans one; otherwise it reuses the existing project.
* **Design review** — `run_design_review` (Stage 46). The pilot blocks unless
  the decision is in `planning_only` / `go_with_findings` / `go` with no
  blocking findings.
* **Workspace operator** — `run_workspace_execution` (Stage 47). The pilot
  reuses its test runs, generated files, and artifacts as acceptance evidence.

## QA evidence

See [qa-safety-evidence.md](qa-safety-evidence.md).

## Acceptance evaluation

See [acceptance-evidence-evaluation.md](acceptance-evidence-evaluation.md).

## Safety evidence

See [qa-safety-evidence.md](qa-safety-evidence.md). Any high-risk flag
(production / GitHub write / PR / deploy / real LLM / external delivery /
repo-root write / secret leak / chain-of-thought) blocks the pilot.

## Mini delivery report

A pilot-level report with executive / project / design-review / workspace / QA
/ acceptance / safety summaries, known limitations, and next steps. It is
**not** the formal Step 47 delivery package; it contains no raw code, no
secrets, and no chain-of-thought.

## Limitations

* One template (`fastapi_todo_service`).
* No real PR, merge, deploy, or external delivery; no real LLM.
* The mini report is a foundation for the Step 47 delivery package, not the
  package itself.

## Safety constraints

Controlled-only throughout; `production_executed` is always false.
`delivery_pilot.*` / `acceptance.*` / `qa_evidence.*` notifications are
default-denied. See
[../operations/mini-delivery-pilot-operations.md](../operations/mini-delivery-pilot-operations.md).
