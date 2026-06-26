# Multi-project Delivery Model (Step 57)

Extends the platform from a single delivery flow to **multiple projects, project-scoped
work items, and tracked dispatch**. **Not** fully autonomous project management /
production delivery automation / multi-tenant production ready.

## Domain
- **projects** (extends the Step 17 planner table) — registry semantics: `project_key`,
  `environment_scope` (dev/test/nonprod), `production_allowed=false`, `registry_status`
  (active/paused/completed/archived).
- **project_work_items** (extended) — adds `lifecycle_state`, `production_effect=false`,
  `requires_human_approval`, `assigned_agent`, `delivery_package_id`.
- **work_item_dispatches**, **work_item_events**, **project_delivery_states**,
  **project_members**, **project_delivery_packages** (new, migration 024).

## SDK
- `shared/sdk/projects` — registry rules + delivery-state rollup + asyncpg store.
- `shared/sdk/work_items` — lifecycle state machine, dispatch resolver, audit/event
  builder, asyncpg store, safety fields.

## API (`/operations/delivery/*`)
GET reads (projects, work items, events, dispatches, delivery-state) + audited writes
(create project, create work item, dispatch). Writes reuse the test-local operator
auth + CSRF + audit and require a reason. See
[multi-project-delivery-dispatch-verification.md](../operations/multi-project-delivery-dispatch-verification.md).

## Safety
No GitHub write, no ArgoCD sync, no external notification send, no production deploy.
`production_effect=true` work items route to `waiting_approval` (never dispatched
directly). `production_executed_true_count=0`. Claude Code does not decide production
readiness.
