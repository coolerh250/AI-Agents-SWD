-- Step AT-M3.5 -- plan-driven delegation: an accepted PlanRevision becomes a durable, dispatchable
-- execution graph.
--
-- Numbering derived from canonical main, which ends at 041 (AT-M3.4). This is 042.
--
-- Implements the slice AT-D14 section 2 authorizes as "M3.5 Plan-driven dynamic delegation":
-- a per-work-item dispatcher over the accepted PlanRevision, reusing the existing AT-M2 capability
-- router unchanged. It decides WHAT executes, WHEN it is ready and WHO receives it. It does not
-- execute anything: no column below holds a command, a diff, a patch, a test result or an external
-- target, and nothing here can acquire one without a further migration and a further decision.
--
-- ------------------------------------------------------------------------------------------
-- THE EXECUTION LINEAGE IS NOT EXTENDED, IT IS POPULATED
-- ------------------------------------------------------------------------------------------
-- source-of-truth-and-lineage-model.md section 1 fixes exactly one autonomous execution lineage:
--
--     Goal -> Project -> Work Item -> Workflow / Run
--
-- and its rule R6 says a Task may REFERENCE that lineage but the lineage must never REQUIRE a Task
-- to advance. So a plan step becomes a WORK ITEM, in the existing `project_work_items` table, and
-- no Task row is written, read or needed anywhere in this slice. at-m1-architecture-reset.md
-- section 3 lists PlanRevision / WorkItem / WorkItemDependency / Ownership as L3's authoritative
-- entities, and planning-and-plan-revision-model.md section 4 already names the pipeline stage
-- this migration serves: "PlanRevision (draft) | work-item generation + dependency generation ->
-- WorkItems + WorkItemDependencies".
--
-- ONE ROOT PER GOAL, ENFORCED BY A PRIMARY KEY. Every step of every revision of one Goal hangs
-- under ONE primary Work Item -- the Goal's autonomous execution root -- recorded in
-- goal_execution_lineage, whose PRIMARY KEY is goal_id. "Which Work Item is this Goal's execution
-- lineage" therefore has exactly one answer and cannot acquire a second, which is the property
-- INV-02 protects. Plan steps become CHILD work items via the existing
-- `project_work_items.parent_work_item_id` column; no unrelated root work item is ever created.
--
-- ------------------------------------------------------------------------------------------
-- WHAT IS REUSED, NOT REBUILT
-- ------------------------------------------------------------------------------------------
--   project_work_items                 THE work item model. A plan step is a child row in it.
--                                      No second work-item entity is defined here.
--   project_work_item_dependencies     THE dependency edges. Plan-step dependencies are ordinary
--                                      work-item edges, already protected by chk_project_dep_no_self
--                                      and uq_project_dep_pair. No second edge table.
--   agent_routing_decisions            THE routing authority and its evidence (AT-M2). Every
--                                      assignment below points at a row in it; no second routing
--                                      table and no second capability registry exists.
--   plan_revisions                     the accepted/current compare-and-swap AT-M3.2 proved. The
--                                      stale-plan protection in this slice is that CAS, reused by
--                                      the service through PlanningStore, not a copy of it.
--   actor_principals                   who a unit is assigned to. A real runtime principal, never
--                                      a name lifted out of plan text.
--   goals / projects                   the lineage anchors.
--
-- Three tables are added, each with one responsibility:
--   goal_execution_lineage      which Work Item is a Goal's single autonomous execution root
--   plan_execution_graphs       one materialization of one accepted PlanRevision
--   plan_execution_units        the plan-step <-> work-item mapping, its runtime state and its
--                               current assignment
--   plan_execution_dispatches   the append-only canonical dispatch ledger
--
-- ------------------------------------------------------------------------------------------
-- THE LOAD-BEARING UNIQUENESS
-- ------------------------------------------------------------------------------------------
--   plan_execution_graphs.plan_revision_id UNIQUE
--       One accepted PlanRevision materializes at most one graph, forever. Eight concurrent
--       materializations of the same revision resolve to one; the losers block on this index,
--       get a unique violation, roll back their whole transaction and replay the winner's graph.
--       Because the entire materialization is ONE transaction, a loser can never leave a partial
--       graph behind.
--
--   plan_execution_units (plan_revision_id, step_key) UNIQUE
--       Exact plan-step identity, preserved durably and per revision. Two revisions may both
--       contain step 'build-api' and they are two different units under two different graphs --
--       there is no step identity collision across revisions, and no unit can ever be rebound
--       from one revision to another (the columns are frozen by trigger).
--
--   plan_execution_dispatches.execution_unit_id PRIMARY KEY
--       One canonical dispatch per execution unit, forever. This is the exactly-once boundary the
--       Redis layer cannot provide: stream delivery is at-least-once and a consumer may see the
--       same command twice, but a second canonical dispatch is not representable. Deliberately
--       NOT (revision, step, generation): no re-dispatch semantics are authorized in this slice,
--       and a generation column that can only ever hold 1 would be a promise the code does not
--       keep. Adding re-dispatch later is a migration and a decision, which is the correct cost.
--
--   plan_execution_units.work_item_id UNIQUE
--       A work item belongs to at most one plan step, so "which step is this work item" is
--       answerable and cannot fork.
--
-- ------------------------------------------------------------------------------------------
-- WHAT IS DERIVED, NOT STORED
-- ------------------------------------------------------------------------------------------
-- Whether a graph's revision is still CURRENT is not a column here, exactly as
-- planning-and-plan-revision-model.md 11b requires: currency has no stored form anywhere in this
-- model, and a copy of it here would be the first -- needing a writer, a race story and a repair
-- path the derived form does not. A superseded graph is recognised by asking
-- plan_revisions whether anything supersedes its revision, and the service does that INSIDE the
-- assignment and dispatch transactions through AT-M3.2's own compare-and-swap. There is no
-- reconciliation daemon, no supersession sweeper and no stale flag.
--
-- Readiness IS stored, because it is not derived from lineage but computed from dependency
-- completion and must be transitioned exactly once under a row lock. `state` is that column.
--
-- ------------------------------------------------------------------------------------------
-- STORAGE PROHIBITION (AT-D03 R8 / INV-04, restated by AT-D14 section 4)
-- ------------------------------------------------------------------------------------------
-- No column below holds a prompt, a completion, hidden reasoning, a scratchpad, a token trace, a
-- discussion transcript, a credential or a raw PlanContent body. `required_capabilities` and
-- `expected_outputs` are the step's own declared contract, copied from a PlanContent that already
-- passed shared/sdk/agent_team/models.py::assert_content_is_safe, and are re-screened by the store
-- before they reach these columns. `unavailable_reason` and `disposition` are short labels from a
-- closed vocabulary. The plan text itself stays in plan_revisions.plan, where AT-M3.2 put it.
--
-- SAFETY: schema only. Starts no container, executes nothing, calls no external provider, creates
-- no Approval and grants no production authorization. Idempotent / re-runnable; a matching
-- *_down.sql reverses it.

BEGIN;

-- ---------------------------------------------------------------------
-- 1. goal_execution_lineage -- which Work Item is this Goal's execution root.
--
--    goal_id is the PRIMARY KEY, which is the whole point: prompt-level "identify which work item
--    is the autonomous Goal execution lineage, no ambiguity" becomes a database fact rather than a
--    convention. primary_work_item_id is UNIQUE so one work item cannot be claimed as the root of
--    two Goals.
--
--    Immutable once written (trigger below). Re-rooting a Goal's execution lineage would silently
--    reparent every graph, assignment and dispatch already recorded under it.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS goal_execution_lineage (
    goal_id               UUID PRIMARY KEY REFERENCES goals(goal_id) ON DELETE CASCADE,
    project_id            UUID NOT NULL,
    primary_work_item_id  UUID NOT NULL REFERENCES project_work_items(id) ON DELETE CASCADE,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Referenced by the composite FK on plan_execution_graphs, so a graph can never claim a goal
    -- that belongs to a different project.
    CONSTRAINT uq_gel_primary_work_item UNIQUE (primary_work_item_id),
    CONSTRAINT uq_gel_goal_project UNIQUE (goal_id, project_id),
    -- The goal must genuinely belong to the project this row claims -- structural, not checked.
    CONSTRAINT fk_gel_goal_project FOREIGN KEY (goal_id, project_id)
        REFERENCES goals (goal_id, project_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_gel_project ON goal_execution_lineage (project_id);

CREATE OR REPLACE FUNCTION goal_execution_lineage_freeze() RETURNS TRIGGER AS $fn$
BEGIN
    RAISE EXCEPTION
        'goal % is already rooted at work item %; an execution lineage is decided once and may '
        'not be re-rooted', OLD.goal_id, OLD.primary_work_item_id
        USING ERRCODE = 'restrict_violation';
END;
$fn$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_gel_freeze ON goal_execution_lineage;
CREATE TRIGGER trg_gel_freeze
    BEFORE UPDATE ON goal_execution_lineage
    FOR EACH ROW EXECUTE FUNCTION goal_execution_lineage_freeze();

-- ---------------------------------------------------------------------
-- 2. plan_execution_graphs -- one materialization of one accepted PlanRevision.
--
--    NOT a Run and NOT a Workflow. source-of-truth-and-lineage-model.md R3 puts a Run under a Work
--    Item and at-m1-architecture-reset.md puts Run/Workflow in L4, which is AT-M4. This slice is
--    L3: it produces the delegation graph a Run will later execute against. Naming this row a Run
--    would claim execution that has not happened, and inventing a PlanRevisionRun would create the
--    second execution instance the architecture forbids.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS plan_execution_graphs (
    plan_execution_graph_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id              UUID NOT NULL,
    goal_id                 UUID NOT NULL,
    -- One graph per accepted PlanRevision, forever. The materialization idempotency boundary.
    plan_revision_id        UUID NOT NULL,
    -- How many units this graph materialized. A plan with no steps has no executable work and is
    -- rejected before it reaches here; the CHECK makes that unrepresentable rather than assumed.
    step_count              INT NOT NULL,
    -- The principal that materialized the graph. NOT NULL: a graph nobody materialized is not
    -- auditable.
    materialized_by         UUID NOT NULL REFERENCES actor_principals(principal_id),
    audit_ref               TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_peg_plan_revision UNIQUE (plan_revision_id),
    CONSTRAINT chk_peg_step_count CHECK (step_count >= 1),
    -- Referenced by the composite FK on plan_execution_units.
    CONSTRAINT uq_peg_id_revision UNIQUE (plan_execution_graph_id, plan_revision_id),
    -- The revision must exist AND belong to the goal this graph claims. Unrepresentable otherwise.
    CONSTRAINT fk_peg_revision_goal FOREIGN KEY (plan_revision_id, goal_id)
        REFERENCES plan_revisions (plan_revision_id, goal_id) ON DELETE CASCADE,
    -- The goal must already have a single primary work item, and it must belong to this project.
    -- A graph therefore cannot exist without the Goal's execution root existing first.
    CONSTRAINT fk_peg_goal_lineage FOREIGN KEY (goal_id, project_id)
        REFERENCES goal_execution_lineage (goal_id, project_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_peg_goal ON plan_execution_graphs (goal_id, created_at);
CREATE INDEX IF NOT EXISTS idx_peg_project ON plan_execution_graphs (project_id, created_at);

-- A graph is a record of a materialization that happened. Nothing about it may be rewritten
-- except the audit reference the sink returns afterwards.
CREATE OR REPLACE FUNCTION plan_execution_graphs_enforce_append_only() RETURNS TRIGGER AS $fn$
BEGIN
    IF NEW.plan_execution_graph_id IS DISTINCT FROM OLD.plan_execution_graph_id
    OR NEW.project_id              IS DISTINCT FROM OLD.project_id
    OR NEW.goal_id                 IS DISTINCT FROM OLD.goal_id
    OR NEW.plan_revision_id        IS DISTINCT FROM OLD.plan_revision_id
    OR NEW.step_count              IS DISTINCT FROM OLD.step_count
    OR NEW.materialized_by         IS DISTINCT FROM OLD.materialized_by
    OR NEW.created_at              IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION
            'plan execution graph % records a materialization already performed and may not be '
            'rewritten; materialize the successor revision instead', OLD.plan_execution_graph_id
            USING ERRCODE = 'restrict_violation';
    END IF;
    IF NEW.audit_ref IS DISTINCT FROM OLD.audit_ref AND OLD.audit_ref IS NOT NULL THEN
        RAISE EXCEPTION
            'plan_execution_graphs.audit_ref is write-once: graph % already carries one',
            OLD.plan_execution_graph_id
            USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NEW;
END;
$fn$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_peg_append_only ON plan_execution_graphs;
CREATE TRIGGER trg_peg_append_only
    BEFORE UPDATE ON plan_execution_graphs
    FOR EACH ROW EXECUTE FUNCTION plan_execution_graphs_enforce_append_only();

-- ---------------------------------------------------------------------
-- 3. plan_execution_units -- the plan step <-> work item mapping, its runtime state and its
--    current assignment.
--
--    STATE VOCABULARY, deliberately small (seven values, no new state machine):
--      blocked     at least one dependency has not completed
--      ready       every dependency has completed (or there were none) -- eligible for assignment
--      assigned    a real, eligible Project-team principal has been routed to it
--      dispatched  the canonical dispatch exists; the command is that principal's
--      completed    the assigned principal reported success through its own dispatch
--      failed      the assigned principal reported failure through its own dispatch
--      cancelled   the Goal's execution lineage was cancelled before this unit finished
--
--    `unavailable_reason` is how "ready, but nobody on this team can take it" is told truthfully
--    (AT-D01's routing contract: a no-eligible-agent answer is never a fallback to a compile-time
--    successor). The unit stays `ready` -- it is genuinely ready, the TEAM is the problem -- so a
--    later schedule call retries assignment once membership or capabilities change, with no
--    polling daemon and no new state.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS plan_execution_units (
    execution_unit_id       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    plan_execution_graph_id UUID NOT NULL,
    plan_revision_id        UUID NOT NULL,
    -- The PlanContent step_key, byte-exact. Structured identity: nothing in this slice matches a
    -- step by title or by prose.
    step_key                TEXT NOT NULL,
    project_id              UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    goal_id                 UUID NOT NULL REFERENCES goals(goal_id) ON DELETE CASCADE,
    -- The child work item this step materialized into. The execution lineage carrier; a Run
    -- created by AT-M4 will resolve to it, satisfying R3 without a second work-item model.
    work_item_id            UUID NOT NULL REFERENCES project_work_items(id) ON DELETE CASCADE,

    -- The step's own declared contract, copied from PlanContent. Arrays of short strings.
    required_capabilities   JSONB NOT NULL DEFAULT '[]'::jsonb,
    expected_outputs        JSONB NOT NULL DEFAULT '[]'::jsonb,
    -- What the PLAN wanted. A preference handed to the AT-M2 router as preferred_role, never an
    -- assignment: plan text cannot forge an ActorPrincipal, and the router ignores a role hint
    -- that matches nobody eligible.
    intended_owner_role     TEXT,

    state                   TEXT NOT NULL DEFAULT 'blocked',
    -- Why a ready unit has no owner. NULL whenever one is assigned.
    unavailable_reason      TEXT,

    -- The current canonical assignment. A real runtime principal, resolved from project team
    -- membership by the AT-M2 router.
    assigned_principal_id   UUID REFERENCES actor_principals(principal_id),
    assigned_role           TEXT,
    assigned_agent_key      TEXT,
    -- Transport only. Says HOW to reach the selected principal, never WHICH principal is next.
    assigned_stream         TEXT,
    -- The AT-M2 routing evidence this assignment rests on: eligible set, rejection reasons and
    -- the reason the winner won. Pointing at it is what keeps a single routing authority.
    routing_decision_id     UUID REFERENCES agent_routing_decisions(routing_decision_id)
                                 ON DELETE SET NULL,
    assigned_at             TIMESTAMPTZ,

    -- The terminal outcome the assigned principal reported, and a reference to its evidence.
    -- A reference, never the evidence body.
    disposition             TEXT,
    result_ref              TEXT,
    completed_at            TIMESTAMPTZ,

    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- EXACT STEP IDENTITY, per revision. The materialization idempotency boundary at step level.
    CONSTRAINT uq_peu_revision_step UNIQUE (plan_revision_id, step_key),
    CONSTRAINT uq_peu_work_item UNIQUE (work_item_id),
    CONSTRAINT chk_peu_step_key CHECK (length(btrim(step_key)) > 0),
    CONSTRAINT chk_peu_state CHECK (state IN (
        'blocked', 'ready', 'assigned', 'dispatched', 'completed', 'failed', 'cancelled'
    )),
    CONSTRAINT chk_peu_capabilities CHECK (jsonb_typeof(required_capabilities) = 'array'),
    CONSTRAINT chk_peu_outputs CHECK (jsonb_typeof(expected_outputs) = 'array'),
    CONSTRAINT chk_peu_disposition CHECK (
        disposition IS NULL OR disposition IN ('succeeded', 'failed')
    ),
    -- An assigned or dispatched unit HAS an owner. This is what stops a dispatch existing with
    -- nobody responsible for it.
    CONSTRAINT chk_peu_assigned_shape CHECK (
        state NOT IN ('assigned', 'dispatched') OR assigned_principal_id IS NOT NULL
    ),
    -- "Nobody can take this" and "this is owned" are mutually exclusive claims.
    CONSTRAINT chk_peu_unavailable_shape CHECK (
        unavailable_reason IS NULL
        OR (state = 'ready' AND assigned_principal_id IS NULL)
    ),
    -- A terminal outcome and its timestamp arrive together or not at all.
    CONSTRAINT chk_peu_terminal_shape CHECK (
        (state IN ('completed', 'failed')) = (completed_at IS NOT NULL)
        AND (state IN ('completed', 'failed')) = (disposition IS NOT NULL)
    ),
    -- The unit's graph must be the graph of the revision it names. A unit cannot be rebound from
    -- one revision's graph to another's, because the pair must exist together.
    CONSTRAINT fk_peu_graph_revision FOREIGN KEY (plan_execution_graph_id, plan_revision_id)
        REFERENCES plan_execution_graphs (plan_execution_graph_id, plan_revision_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_peu_graph_state
    ON plan_execution_units (plan_execution_graph_id, state);
CREATE INDEX IF NOT EXISTS idx_peu_goal ON plan_execution_units (goal_id, created_at);
CREATE INDEX IF NOT EXISTS idx_peu_assigned
    ON plan_execution_units (assigned_principal_id, state);
CREATE INDEX IF NOT EXISTS idx_peu_work_item ON plan_execution_units (work_item_id);

-- The unit's IDENTITY is frozen; only its runtime state and assignment may move. Rewriting
-- plan_revision_id or step_key would rebind already-recorded work from one revision to another,
-- which section 20 of the slice contract forbids outright -- so it is made impossible rather than
-- merely avoided.
CREATE OR REPLACE FUNCTION plan_execution_units_freeze_identity() RETURNS TRIGGER AS $fn$
BEGIN
    IF NEW.execution_unit_id       IS DISTINCT FROM OLD.execution_unit_id
    OR NEW.plan_execution_graph_id IS DISTINCT FROM OLD.plan_execution_graph_id
    OR NEW.plan_revision_id        IS DISTINCT FROM OLD.plan_revision_id
    OR NEW.step_key                IS DISTINCT FROM OLD.step_key
    OR NEW.project_id              IS DISTINCT FROM OLD.project_id
    OR NEW.goal_id                 IS DISTINCT FROM OLD.goal_id
    OR NEW.work_item_id            IS DISTINCT FROM OLD.work_item_id
    OR NEW.required_capabilities   IS DISTINCT FROM OLD.required_capabilities
    OR NEW.expected_outputs        IS DISTINCT FROM OLD.expected_outputs
    OR NEW.intended_owner_role     IS DISTINCT FROM OLD.intended_owner_role
    OR NEW.created_at              IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION
            'execution unit % is bound to plan revision % step %; its plan identity may not be '
            'rewritten -- materialize the successor revision instead',
            OLD.execution_unit_id, OLD.plan_revision_id, OLD.step_key
            USING ERRCODE = 'restrict_violation';
    END IF;
    -- A terminal unit is evidence. Nothing moves it again, including a later cancellation:
    -- work that finished under revision N stays finished when N+1 appears.
    IF OLD.state IN ('completed', 'failed', 'cancelled')
       AND NEW.state IS DISTINCT FROM OLD.state THEN
        RAISE EXCEPTION
            'execution unit % is already %; a terminal unit may not be moved again',
            OLD.execution_unit_id, OLD.state
            USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NEW;
END;
$fn$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_peu_freeze_identity ON plan_execution_units;
CREATE TRIGGER trg_peu_freeze_identity
    BEFORE UPDATE ON plan_execution_units
    FOR EACH ROW EXECUTE FUNCTION plan_execution_units_freeze_identity();

-- ---------------------------------------------------------------------
-- 4. plan_execution_dispatches -- the append-only canonical dispatch ledger.
--
--    execution_unit_id is the PRIMARY KEY: one canonical dispatch per unit, forever. This is the
--    exactly-once guarantee, and it is honest about where it stops. Redis Streams deliver
--    at-least-once and a consumer may see one command twice; what cannot happen is a SECOND
--    CANONICAL DISPATCH, because there is no second row to write. A redelivered command carries
--    the same correlation_id, resolves to the same row, and is therefore recognisable as the same
--    dispatch rather than a new one.
--
--    published_at records whether the transport actually carried it. It is NULL when the row was
--    committed but the stream publish had not yet succeeded -- a crash window that genuinely
--    exists, because a Redis XADD cannot join a PostgreSQL transaction. Recording it is what lets
--    a later schedule call re-publish the SAME dispatch instead of minting a new one, which is
--    exactly the at-least-once transport / exactly-once canonical state split.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS plan_execution_dispatches (
    execution_unit_id     UUID PRIMARY KEY
                               REFERENCES plan_execution_units(execution_unit_id) ON DELETE CASCADE,
    -- The exact PlanRevision that authorized this dispatch, and the exact step. Immutable, on an
    -- immutable row: a dispatch can never be rebound from revision N to N+1.
    plan_revision_id      UUID NOT NULL
                               REFERENCES plan_revisions(plan_revision_id) ON DELETE CASCADE,
    step_key              TEXT NOT NULL,
    project_id            UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    work_item_id          UUID NOT NULL REFERENCES project_work_items(id) ON DELETE CASCADE,
    assigned_principal_id UUID NOT NULL REFERENCES actor_principals(principal_id),
    routing_decision_id   UUID REFERENCES agent_routing_decisions(routing_decision_id)
                               ON DELETE SET NULL,
    target_stream         TEXT NOT NULL,
    -- The stable idempotency identity carried on the wire. A consumer that has already applied
    -- this correlation id knows a redelivery when it sees one.
    correlation_id        UUID NOT NULL DEFAULT uuid_generate_v4(),
    published_at          TIMESTAMPTZ,
    audit_ref             TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_ped_correlation UNIQUE (correlation_id),
    CONSTRAINT chk_ped_stream CHECK (length(btrim(target_stream)) > 0),
    CONSTRAINT chk_ped_step_key CHECK (length(btrim(step_key)) > 0)
);

CREATE INDEX IF NOT EXISTS idx_ped_revision ON plan_execution_dispatches (plan_revision_id);
CREATE INDEX IF NOT EXISTS idx_ped_principal
    ON plan_execution_dispatches (assigned_principal_id, created_at);
CREATE INDEX IF NOT EXISTS idx_ped_unpublished
    ON plan_execution_dispatches (created_at) WHERE published_at IS NULL;

-- A dispatch is a record of work already handed to a principal. Only two facts may be added to it
-- afterwards, and both are write-once bookkeeping: that the transport carried it, and the audit
-- reference the sink returned.
CREATE OR REPLACE FUNCTION plan_execution_dispatches_enforce_append_only() RETURNS TRIGGER AS $fn$
BEGIN
    IF NEW.execution_unit_id     IS DISTINCT FROM OLD.execution_unit_id
    OR NEW.plan_revision_id      IS DISTINCT FROM OLD.plan_revision_id
    OR NEW.step_key              IS DISTINCT FROM OLD.step_key
    OR NEW.project_id            IS DISTINCT FROM OLD.project_id
    OR NEW.work_item_id          IS DISTINCT FROM OLD.work_item_id
    OR NEW.assigned_principal_id IS DISTINCT FROM OLD.assigned_principal_id
    OR NEW.routing_decision_id   IS DISTINCT FROM OLD.routing_decision_id
    OR NEW.target_stream         IS DISTINCT FROM OLD.target_stream
    OR NEW.correlation_id        IS DISTINCT FROM OLD.correlation_id
    OR NEW.created_at            IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION
            'dispatch for execution unit % was issued to principal % under plan revision % and '
            'may not be rewritten', OLD.execution_unit_id, OLD.assigned_principal_id,
            OLD.plan_revision_id
            USING ERRCODE = 'restrict_violation';
    END IF;
    IF NEW.published_at IS DISTINCT FROM OLD.published_at AND OLD.published_at IS NOT NULL THEN
        RAISE EXCEPTION
            'plan_execution_dispatches.published_at is write-once for execution unit %',
            OLD.execution_unit_id
            USING ERRCODE = 'restrict_violation';
    END IF;
    IF NEW.audit_ref IS DISTINCT FROM OLD.audit_ref AND OLD.audit_ref IS NOT NULL THEN
        RAISE EXCEPTION
            'plan_execution_dispatches.audit_ref is write-once for execution unit %',
            OLD.execution_unit_id
            USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NEW;
END;
$fn$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_ped_append_only ON plan_execution_dispatches;
CREATE TRIGGER trg_ped_append_only
    BEFORE UPDATE ON plan_execution_dispatches
    FOR EACH ROW EXECUTE FUNCTION plan_execution_dispatches_enforce_append_only();

COMMIT;
