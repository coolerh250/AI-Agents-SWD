# Project Delivery-state Model (Step 57)

Project delivery state is a deterministic rollup of work-item lifecycle states:
not_started, intake_active, planning_active, implementation_active, qa_active,
packaging_active, operator_review, completed_nonproduction, blocked, cancelled. See
[`infra/delivery/project-delivery-state-model.yaml`](../../infra/delivery/project-delivery-state-model.yaml)
and `shared/sdk/projects.compute_delivery_state`.

Any blocked work item ⇒ project blocked; any waiting_approval ⇒ operator_review.
`completed_nonproduction` is **not** a production release; `productionReady=false`; no
auto-release.
