-- Reverses 042_at_m3_5_plan_execution_graph.sql.
--
-- Drops the four AT-M3.5 tables and their trigger functions, in dependency order. Nothing in
-- AT-M2, AT-M3.2, AT-M3.3 or AT-M3.4 is touched, because the forward migration added nothing to
-- them: projects, project_work_items, project_work_item_dependencies, agent_routing_decisions,
-- actor_principals, goals and plan_revisions are left exactly as they were, with the same columns
-- and the same constraints.
--
-- Note what this deliberately does NOT undo. The CHILD WORK ITEMS a materialization created, and
-- the DEPENDENCY EDGES between them, stay. They are ordinary rows in the existing
-- project_work_items / project_work_item_dependencies tables and belong to the project's own
-- execution lineage, not to this slice's bookkeeping -- the same reason 041's down migration
-- leaves behind the TeamDecisions and accepted PlanRevisions its ledger produced, and 039's
-- leaves the threads and messages a discussion produced. The routing decisions recorded in
-- agent_routing_decisions stay for the same reason: they are AT-M2's evidence of who the team
-- chose, not this migration's private state.
--
-- What is lost is the ability to answer "which plan step is this work item, and was it
-- dispatched" -- and nothing else. A re-run of the forward migration followed by a fresh
-- materialization would produce a NEW graph with NEW child work items rather than re-adopting the
-- orphaned ones, which is correct: adopting rows whose provenance was deleted is exactly the kind
-- of quiet reattachment this model refuses everywhere else.
--
-- Data loss is intentional and total for the four tables below -- this is a down migration for a
-- non-production environment, not an archival step.

BEGIN;

DROP TRIGGER IF EXISTS trg_ped_append_only ON plan_execution_dispatches;
DROP TABLE IF EXISTS plan_execution_dispatches;
DROP FUNCTION IF EXISTS plan_execution_dispatches_enforce_append_only();

DROP TRIGGER IF EXISTS trg_peu_freeze_identity ON plan_execution_units;
DROP TABLE IF EXISTS plan_execution_units;
DROP FUNCTION IF EXISTS plan_execution_units_freeze_identity();

DROP TRIGGER IF EXISTS trg_peg_append_only ON plan_execution_graphs;
DROP TABLE IF EXISTS plan_execution_graphs;
DROP FUNCTION IF EXISTS plan_execution_graphs_enforce_append_only();

DROP TRIGGER IF EXISTS trg_gel_freeze ON goal_execution_lineage;
DROP TABLE IF EXISTS goal_execution_lineage;
DROP FUNCTION IF EXISTS goal_execution_lineage_freeze();

COMMIT;
