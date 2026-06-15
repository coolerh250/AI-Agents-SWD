# Delivery Package & Acceptance Gate (Step 47 / Stage 49)

## Purpose

Turn a completed **Mini Project Delivery Pilot** (Step 46) into a formal,
human-reviewable **Delivery Package** plus an **Acceptance Gate**. This is the
hand-off boundary between the controlled, automated pipeline and a human
operator / business owner who decides whether to accept the delivery.

This stage is **controlled-only**. It is *not* production delivery, *not* a real
GitHub PR, *not* a deploy, and *not* external communication. It produces an
inspectable package and a gate result that is **`ready_for_operator_review`** —
it never auto-marks human acceptance.

## Package build path

```
Mini Delivery Pilot (completed)
  → collect artifacts (project / design / workspace / QA / safety / acceptance / report)
  → build acceptance checklist
  → build 14 package sections
  → evaluate acceptance gate (18 checks)
  → operator acceptance review placeholder (pending)
  → handoff summaries (business / technical / operator)
  → delivery readiness snapshot
  → delivery package report + export metadata
  → status = ready_for_review  (human_acceptance_status = pending)
```

The builder reuses already-persisted pilot evidence — it never re-runs code
generation or tests, never calls an LLM, and never writes externally.

## Package sections

14 required sections, each `ready` / `missing` / `failed`:

`executive_summary`, `scope_and_non_scope`, `project_plan`,
`design_review_summary`, `implementation_summary`, `generated_files_manifest`,
`test_results`, `qa_summary`, `safety_summary`, `acceptance_checklist`,
`known_limitations`, `run_instructions`, `handoff_notes`, `next_steps`.

The `generated_files_manifest` carries relative paths + content hashes + sizes
only — never file bodies.

## Artifact model

`delivery_package_artifacts` links the source evidence by reference (opaque
ids + counts + short summaries): `project_brief`, `task_graph`,
`design_review_summary`, `workspace_report`, `generated_code_manifest`,
`test_result`, `qa_evidence_report`, `safety_evidence_report`,
`acceptance_evaluations`, `mini_delivery_report`. No raw code is stored.

## Acceptance gate

`acceptance_gate_runs` + `acceptance_gate_check_results`. 18 deterministic
checks across `project` / `design_review` / `workspace` / `testing` /
`acceptance` / `qa` / `safety` / `documentation` / `governance` /
`human_review`:

- blocking technical/safety/governance checks: `project_brief_exists`,
  `task_graph_valid`, `design_review_completed`, `no_blocking_design_findings`,
  `workspace_generated`, `tests_passed`, `acceptance_criteria_satisfied`,
  `safety_report_safe`, `no_github_write`, `no_pr_created`, `no_deploy`,
  `no_production_execution`, `no_secret_leak`
- non-blocking: `qa_report_passed`, `delivery_sections_complete`,
  `known_limitations_documented`, `run_instructions_present`
- `human_acceptance_pending` — a **warning**, never blocking, never auto-checked

Gate resolution:

| Condition | status | decision |
|---|---|---|
| any blocking check failed / tests failed / acceptance failed / unsafe | `blocked` | `needs_changes` / `blocked` |
| all technical checks pass, warnings present (incl. human pending) | `passed_with_findings` | `ready_for_operator_review` |
| all technical checks pass, no warnings | `passed` | `ready_for_operator_review` |

The gate **never** returns `decision=accepted`.

## Human review pending model

See [operator-acceptance-review.md](operator-acceptance-review.md). A pending
`operator_acceptance_reviews` row is created on every build. Accept / reject /
request-changes endpoints are **disabled by default**
(`ENABLE_DELIVERY_PACKAGE_OPERATOR_ACTIONS=false`).

## Readiness snapshot

See [delivery-readiness-model.md](delivery-readiness-model.md).

## Controlled-only mode

Every real-write flag defaults false; `production_executed` is always false:
`delivery_package_controlled_only`, `real_llm`, `github_write`, `pr_creation`,
`deploy`, `external_delivery`, `auto_accept`, `operator_actions`.

## Limitations

- No authentication, SQLite only, no production deployment config.
- No real GitHub PR / merge / branch push this stage.
- No external delivery / notification this stage.
- Generated workspace files are never committed to the main repo.

## Safety constraints

- `production_executed=true` count must remain 0.
- `delivery_package.*` / `acceptance_gate.*` / `handoff.*` notifications are
  default-denied (never reach real Discord / Slack / Telegram).
- No secrets, no chain-of-thought, no raw code persisted; only summaries,
  checklists, evidence refs.
- Claude Code reports observations only; it never declares production readiness.
