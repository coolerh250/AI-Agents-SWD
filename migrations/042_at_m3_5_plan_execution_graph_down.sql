-- Reverses 042_at_m3_5_plan_execution_graph.sql -- but ONLY while nothing has been materialized.
--
-- ------------------------------------------------------------------------------------------
-- WHY THIS DOWN MIGRATION REFUSES
-- ------------------------------------------------------------------------------------------
-- The forward migration deliberately does not own the work items a plan step becomes: those are
-- ordinary `project_work_items` rows in the project's own execution lineage, and 041's down
-- migration takes the same posture toward the TeamDecisions and PlanRevisions its ledger produced.
--
-- That posture is right for a ledger and wrong for a MAPPING. The first cut of this file dropped
-- the four tables and left the child work items and their dependency edges behind, and reasoned
-- that a later re-UP would simply build a new graph rather than re-adopt orphans. It would -- and
-- that is the defect. The dropped tables ARE the only record of which work item is which plan step:
--
--     DOWN   ->  plan-step <-> work-item identity is destroyed; the work items survive, now
--                unattributable
--     UP     ->  empty schema; uq_peu_revision_step has nothing to collide with
--     materialize the SAME accepted PlanRevision
--            ->  materialization is idempotent against the GRAPH, and the graph is gone, so it
--                is not a replay: a second full set of child work items and dependency edges is
--                created under the same primary Work Item, for the same steps of the same plan
--
-- The result is duplicated business work in the canonical execution lineage, produced by a
-- supported migration sequence, with nothing in the schema able to detect it afterwards. Neither
-- available repair is acceptable: deleting the work items on DOWN would destroy execution-lineage
-- rows this slice does not own (and, once AT-M4 exists, Runs and artifacts resolving to them),
-- while re-adopting orphans on UP would reattach work whose provenance was deleted -- exactly the
-- quiet reattachment this model refuses everywhere else.
--
-- So the sequence is removed rather than repaired. Once ANY materialization evidence exists, this
-- migration RAISES and the transaction rolls back: schema, mappings, dispatches, work items and
-- edges all survive untouched, and the operator is told plainly that the downgrade would destroy
-- plan-step identity. A non-production environment that genuinely wants the schema gone can drop
-- the database, which is honest about what it costs.
--
-- WHAT REFUSAL DOES NOT MEAN. This is not an exemption mechanism, an override or a
-- force flag, and nothing can invoke it to excuse a later row. It is one CHECK on one downgrade
-- path, and its only outcome is "refuse and change nothing".
--
-- ------------------------------------------------------------------------------------------
-- WHEN IT PROCEEDS
-- ------------------------------------------------------------------------------------------
-- With all four tables empty there is no identity to lose, so UP / DOWN / UP / UP on a fresh
-- database is clean and re-runnable, which is what a migration rehearsal actually exercises.
--
-- Nothing in AT-M2, AT-M3.2, AT-M3.3 or AT-M3.4 is touched either way: the forward migration added
-- nothing to them, and `projects`, `project_work_items`, `project_work_item_dependencies`,
-- `agent_routing_decisions`, `work_item_events`, `actor_principals`, `goals` and `plan_revisions`
-- are left exactly as they were, with the same columns and the same constraints.

BEGIN;

-- ---------------------------------------------------------------------
-- 1. Fail closed if this database holds any AT-M3.5 materialization evidence.
--
--    Guarded on to_regclass so a partially-applied or already-reversed database reports "nothing
--    to lose" instead of erroring on a missing table.
-- ---------------------------------------------------------------------
DO $$
DECLARE
    lineage_rows  BIGINT := 0;
    graph_rows    BIGINT := 0;
    unit_rows     BIGINT := 0;
    dispatch_rows BIGINT := 0;
BEGIN
    IF to_regclass('public.goal_execution_lineage') IS NOT NULL THEN
        EXECUTE 'SELECT count(*) FROM goal_execution_lineage' INTO lineage_rows;
    END IF;
    IF to_regclass('public.plan_execution_graphs') IS NOT NULL THEN
        EXECUTE 'SELECT count(*) FROM plan_execution_graphs' INTO graph_rows;
    END IF;
    IF to_regclass('public.plan_execution_units') IS NOT NULL THEN
        EXECUTE 'SELECT count(*) FROM plan_execution_units' INTO unit_rows;
    END IF;
    IF to_regclass('public.plan_execution_dispatches') IS NOT NULL THEN
        EXECUTE 'SELECT count(*) FROM plan_execution_dispatches' INTO dispatch_rows;
    END IF;

    IF (lineage_rows + graph_rows + unit_rows + dispatch_rows) > 0 THEN
        RAISE EXCEPTION
            'refusing to reverse migration 042: this database holds AT-M3.5 materialization '
            'evidence (% goal execution lineage row(s), % graph(s), % execution unit(s), '
            '% dispatch(es)). Dropping these tables would destroy the only record of which '
            'project_work_items row is which plan step, while leaving those work items and their '
            'dependency edges in place -- so a later re-apply plus a re-materialization of the '
            'same PlanRevision would create a SECOND set of child work items for the same steps. '
            'Nothing has been changed. Drop the database instead if the schema must go.',
            lineage_rows, graph_rows, unit_rows, dispatch_rows
            USING ERRCODE = 'restrict_violation';
    END IF;
END
$$;

-- ---------------------------------------------------------------------
-- 2. Nothing was materialized, so nothing is lost. Drop in dependency order.
-- ---------------------------------------------------------------------
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
