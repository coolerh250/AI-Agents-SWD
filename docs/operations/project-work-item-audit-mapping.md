# Project / Work-item Audit Mapping (Step 57)

Audit events for project/work-item/dispatch lifecycle (project_created,
work_item_created, work_item_triaged, work_item_dispatched, work_item_blocked,
work_item_completed, work_item_failed, delivery_package_linked,
project_delivery_state_updated). See
[`infra/delivery/project-work-item-audit-mapping.yaml`](../../infra/delivery/project-work-item-audit-mapping.yaml)
and `shared/sdk/work_items/events.py`.

Required metadata: actor / role / reason / project_id / work_item_id / correlation_id.
Forbidden metadata (dropped by the builder): secret, token, password, chain_of_thought,
raw_reasoning. `production_executed=false`.
