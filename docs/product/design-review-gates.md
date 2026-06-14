# Design Review Gates (Stage 46)

Gates are project-level checkpoints derived from the review context + findings.
Each gate is persisted in `project_review_gates` (unique per
`(project_id, gate_type)`).

## Gates

| Gate | Passes when | Relevant findings |
|---|---|---|
| `requirement_gate` | brief has scope + non-scope + user stories | requirement_gap, scope_risk |
| `architecture_gate` | an architecture or backend work item exists | architecture_risk |
| `implementation_strategy_gate` | development work items exist AND graph is valid | implementation_risk, dependency_issue |
| `qa_strategy_gate` | a QA work item + acceptance criteria exist | qa_gap, acceptance_gap |
| `security_gate` | always evaluated; status driven by findings | security_risk |
| `delivery_gate` | a release/delivery work item exists | delivery_risk |
| `pre_execution_gate` | no other gate is blocked | (aggregate) |

## Gate status

For each gate, from the relevant **open** findings:

* a **critical** relevant finding, or a failed structural check → `blocked`
* any open relevant finding (low/medium/high) → `passed_with_findings`
* otherwise → `passed`

`pre_execution_gate` is `blocked` if any gate is blocked, else
`passed_with_findings` when any open findings exist, else `passed`. This stage is
planning-only, so even a clean pre-execution gate does not dispatch execution.

## Finding severity model

`low` < `medium` < `high` < `critical`. Findings carry a `finding_type`,
`severity`, `status` (`open` / `accepted` / `mitigated` / `waived` / `closed`),
a title, description, and recommendation. An `accepted` finding (e.g. "lack of
auth is an accepted non-scope item") does not downgrade a gate.

## Go / No-Go decision logic

Evaluated over **open** findings + gate statuses:

1. any **critical** finding OR any **blocked** gate → `no_go` (status `blocked`)
2. else any open **high** `requirement_gap` → `needs_clarification` (blocked)
3. else if planning-only (this stage) OR dispatch disabled → `planning_only`
   (status `passed` / `passed_with_findings`)
4. else (dispatch enabled, future) → `go_with_findings` if any open findings,
   else `go`

## Blocking rules

* `no_go` and `needs_clarification` set the workflow stage to
  `design_review_blocked` and never dispatch development.
* `go_with_findings` → `design_reviewed_with_findings` (no dispatch this stage).
* `go` / `planning_only` → `design_reviewed` (no dispatch this stage unless
  `ENABLE_PROJECT_WORK_ITEM_DISPATCH` is later enabled).

## Expected result for the FastAPI Todo template

`planning_only` decision, 0 blocking findings, no critical findings; gates:
requirement/architecture/implementation/qa/delivery `passed`, security +
pre-execution `passed_with_findings`.
