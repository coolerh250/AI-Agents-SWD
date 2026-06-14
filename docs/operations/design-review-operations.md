# Design Review Operations (Stage 46)

Read-only discussion/review visibility plus one review-only write endpoint, all
under `/operations/*` on the orchestrator (port 8000).

## Endpoints

### Run review (write — review-only)
* `POST /operations/projects/{project_id}/design-review` — runs the deterministic
  multi-role review against the planned graph, persists findings/decisions/gates,
  returns the `DesignReviewOutput`. Never calls an LLM, writes GitHub, deploys,
  or dispatches work items.

### Discussion reads
* `GET /operations/projects/{project_id}/discussions`
* `GET /operations/discussions/{session_id}`
* `GET /operations/discussions/{session_id}/participants`
* `GET /operations/discussions/{session_id}/contributions`
* `GET /operations/discussions/{session_id}/artifacts`

### Design review reads
* `GET /operations/projects/{project_id}/design-reviews`
* `GET /operations/design-reviews/{review_session_id}`
* `GET /operations/design-reviews/{review_session_id}/findings`
* `GET /operations/design-reviews/{review_session_id}/decisions`
* `GET /operations/projects/{project_id}/review-gates`
* `GET /operations/projects/{project_id}/go-no-go-summary`
* `GET /operations/projects/{project_id}/acceptance-coverage`

## Safety surface (`GET /operations/safety`)

New fields: `design_review_enabled`, `design_review_planning_only` (expected
`true`), `design_review_real_llm_enabled` (`false`),
`design_review_work_item_dispatch_enabled` (`false`),
`agent_discussion_enabled`,
`agent_discussion_chain_of_thought_persistence_enabled` (`false`),
`latest_design_review_status`, `latest_design_review_decision`,
`latest_design_review_project_id`, `latest_design_review_findings_count`,
`latest_design_review_blocking_findings_count`,
`latest_project_review_gates_status`, `project_pre_execution_gate_passed`.

## Verify

`scripts/verify_agent_discussion_design_review.sh` exercises service health, a
FastAPI Todo plan + review, the operations API, planning-only safety,
audit/notification denylisting, and full-regression compatibility. Marker:
`AGENT_DISCUSSION_DESIGN_REVIEW_VERIFY: PASS`. Runtime smokes 165–177 in
`check_runtime_state.sh` cover the same surfaces.

## Safety notes

* All read endpoints are side-effect free.
* No response carries a secret or chain-of-thought; only findings / gates /
  decisions / summaries.
* `discussion.*` and `design_review.*` notification events are blocked from real
  delivery by the default denylist.
