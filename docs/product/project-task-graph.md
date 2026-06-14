# Project Task Graph (Stage 45)

The data model behind the project planner. Migration
`017_project_planner_task_graph.sql` adds ten additive tables; no existing
workflow table is modified.

## Models

### Project (`projects`)
Parent project per request. `status ∈ {draft, planning, planned, in_progress,
blocked, qa, delivery_ready, accepted, cancelled, failed}`,
`autonomy_level ∈ {advisory, assisted, autonomous_dev_test, production_gated}`,
`risk_level ∈ {low, medium, high, production}`.

### Brief (`project_briefs`)
`problem_statement`, `goal`, `scope`, `non_scope`, `assumptions`, `constraints`,
`stakeholders`, `success_metrics` (all JSONB lists). `requires_clarification` is
carried in `metadata`.

### User story (`project_user_stories`)
`actor` / `need` / `benefit` / `priority` / `status`.

### Acceptance criterion (`project_acceptance_criteria`)
`description`, `verification_method ∈ {unit_test, integration_test, e2e_test,
manual_review, static_check, documentation_review}`, `status ∈ {pending,
satisfied, failed, waived}`, `required`, optional `work_item_id`.

### Milestone (`project_milestones`)
`milestone_key`, `title`, `order_index`, `status ∈ {pending, in_progress,
completed, blocked, cancelled}`.

### Work item (`project_work_items`) — graph node
`work_type ∈ {requirement, architecture, backend, frontend, database,
integration, qa, security, devops, documentation, release}`,
`assigned_agent_role`, `status ∈ {pending, ready, in_progress, blocked, review,
completed, failed, cancelled}`, `priority ∈ {low, medium, high, critical}`,
`risk_level`, `dispatch_policy ∈ {planning_only, auto_dev_test_allowed,
approval_required}`, optional `milestone_id` / `parent_work_item_id`.

### Dependency (`project_work_item_dependencies`) — graph edge
`work_item_id`, `depends_on_work_item_id`, `dependency_type ∈ {blocks, informs,
requires_output, review_after}`. DB constraints forbid self-dependency
(`chk_project_dep_no_self`) and duplicates (`uq_project_dep_pair`).

### Risk (`project_risks`)
`severity ∈ {low, medium, high, critical}`, `likelihood ∈ {low, medium, high}`,
`status ∈ {open, mitigated, accepted, closed}`, `owner_agent_role`.

### Artifact (`project_artifacts`)
`artifact_type` (project_brief / task_graph / qa_report / delivery_summary / …),
optional `content` JSONB, `uri`, `work_item_id`.

### Graph snapshot (`project_graph_snapshots`)
One row per build: `graph_hash`, `nodes`, `edges`,
`validation_status ∈ {valid, invalid, warning}`, `validation_errors`.

## Graph validation rules

1. No self-dependency (`a == b`).
2. No duplicate `(work_item, depends_on)` pair.
3. Every dependency endpoint must reference an existing node.
4. No cycles (DFS back-edge detection).
5. Isolated nodes → `warning` (not a hard failure).

A `valid` or `warning` graph is persisted and the project becomes `planned`;
an `invalid` graph sets the workflow stage to `planning_failed`.

## Status transitions (planning-only this stage)

```
project:    draft ─┐
                   └─(plan)→ planning ─→ planned
                   └─(vague)→ draft (clarification_needed)
work item:  pending → ready → in_progress → review → completed
                    ↘ blocked        ↘ failed / cancelled
workflow:   in_progress ─(project.planning_completed)→ project_planned
                        ─(invalid / failed)→ planning_failed
                        ─(clarification)→ project_clarification_required
```

Work-item dispatch (`ready → in_progress` driven by an agent) is gated behind
`ENABLE_PROJECT_WORK_ITEM_DISPATCH` and is **off** this stage.
