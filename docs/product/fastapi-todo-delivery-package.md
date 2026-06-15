# FastAPI Todo Delivery Package (Stage 49 worked example)

The acceptance example for Step 47 builds a formal delivery package from the
Step 46 FastAPI Todo mini delivery pilot.

## Source mini pilot

Request: *"Create a FastAPI Todo Service with CRUD, SQLite, pytest, README, and
API examples."* The pilot must be `completed` / `report_ready` with acceptance
failed = 0, QA `passed` / `passed_with_findings`, and safety `safe`.

Build:

```bash
curl -X POST \
  http://localhost:8000/operations/mini-delivery-pilots/$PILOT_ID/delivery-package/build
```

## Package sections

All 14 sections `ready` (0 missing): executive summary, scope/non-scope,
project plan, design review summary, implementation summary, generated files
manifest (paths + hashes), test results, QA summary, safety summary, acceptance
checklist, known limitations, run instructions, handoff notes, next steps.

## Acceptance checks (expected)

`passed` (blocking unless noted): `project_brief_exists`, `task_graph_valid`,
`design_review_completed`, `no_blocking_design_findings`, `workspace_generated`,
`tests_passed`, `acceptance_criteria_satisfied`, `qa_report_passed` (non-blocking),
`safety_report_safe`, `no_github_write`, `no_pr_created`, `no_deploy`,
`no_production_execution`, `no_secret_leak`, `delivery_sections_complete`,
`known_limitations_documented`, `run_instructions_present`.

`warning` (non-blocking): `human_acceptance_pending`.

Gate: `status=passed_with_findings`, `decision=ready_for_operator_review`,
`human_review_status=pending`, `blocking_findings_count=0`, `failed_checks=0`.

## Handoff summary

Three summaries are produced: `business_summary` (non-technical),
`technical_summary` (files / tests / limitations), `operator_summary` (review
items + next steps).

## Known limitations

No auth; local SQLite only; no production deployment; no real PR this stage; no
external delivery; controlled-only workspace.

## How to inspect the package

```bash
P=http://localhost:8000/operations/delivery-packages/$PACKAGE_ID
curl -s $P/sections        # 14 sections, missing_count=0
curl -s $P/artifacts       # linked source artifacts
curl -s $P/acceptance-gate # passed_with_findings / ready_for_operator_review
curl -s $P/acceptance-checks
curl -s $P/acceptance-checklist
curl -s $P/readiness       # ready_for_operator_review, human pending
curl -s $P/handoff-summaries
curl -s $P/operator-review # pending
curl -s $P/report
```
