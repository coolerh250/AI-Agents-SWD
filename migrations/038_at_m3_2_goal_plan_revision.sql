-- Step AT-M3.2 -- Goal + immutable PlanRevision.
--
-- Implements docs/architecture/autonomous-team/planning-and-plan-revision-model.md sections 2 and
-- 3 (AT-D04), authorized for implementation by AT-D14. Two new tables plus exactly one authorized
-- alteration of an AT-M2 table.
--
-- SCOPE (AT-D14): AT-D14 pre-cleared precisely two things beyond additive tables --
-- "the Goal/PlanRevision schema M3.2 introduces" and the FK
-- `team_decisions.resulting_plan_revision_id -> plan_revisions.plan_revision_id`. Nothing else on
-- any AT-M2 table is touched here. No M3.3+ behaviour (discussion, proposal/challenge,
-- decomposition, dispatch) has a column in this migration.
--
-- IMMUTABILITY (D04-R1/R3, INV-05): a plan_revisions row is append-only. Changing a plan creates
-- revision N+1 naming N as its predecessor; it never UPDATEs N. This is enforced at the DATABASE
-- layer by trg_plan_revisions_immutable below, not only by the service, because a direct SQL
-- caller bypasses the service entirely -- the same defence-in-depth reasoning
-- `TeamStore.post_message` applies to content safety.
--
-- SUPERSESSION IS DERIVED, NOT STORED: `status` deliberately does NOT carry a 'superseded' value.
-- A revision is superseded exactly when another revision names it in supersedes_revision_id, which
-- is a fact about the lineage and needs no write to the predecessor. Storing it as a mutable
-- status would require an UPDATE on an append-only row to express something the data already
-- says. The architecture contract lists 'superseded' among the statuses; this implementation keeps
-- that MEANING and derives it.
--
-- ACCEPTANCE IS A REAL TRANSITION ON THE SAME ROW: `status` covers draft/proposed/accepted/
-- rejected, and exactly one transition is authorized -- draft -> accepted -- because that is the
-- one the approved pipeline names (section 4). It is enforced by the lifecycle trigger below, not
-- by convention. This is the correction AT-M3.2 Validation 1 required: the first cut froze status
-- from creation, which made the pipeline's own team-acceptance stage unreachable.
--
-- REVISION NUMBERING: monotonic PER PROJECT, exactly as the contract specifies twice ("revision
-- _number 1, 2, 3 ... monotonic per project", "VERSIONED revision_number is monotonic per
-- project"). A project with two Goals therefore shares one revision sequence across them, and
-- lineage (which revision supersedes which) is scoped per GOAL by the composite FK below. Those
-- are two different guarantees and both are enforced here.
--
-- STALE-PLAN PROTECTION: uq_plan_revisions_one_successor is the primitive. At most ONE revision
-- may ever name a given predecessor, so two concurrent callers deriving a successor from the same
-- current revision cannot both win -- the loser gets a unique violation, which the store maps to a
-- fail-closed conflict. The service additionally takes FOR UPDATE on the predecessor, so the
-- common path serialises cleanly rather than relying on the constraint as the only gate; the
-- constraint is what makes the guarantee true even for a caller that bypasses the service.
--
-- CROSS-GOAL / CROSS-PROJECT REJECTION IS STRUCTURAL: rather than a trigger or an application
-- check, two composite foreign keys make a mismatched lineage unrepresentable --
-- (supersedes_revision_id, goal_id) must reference an EXISTING revision of the SAME goal, and
-- (goal_id, project_id) must reference a goal that genuinely belongs to that project.
--
-- CYCLES ARE IMPOSSIBLE BY CONSTRUCTION: supersedes_revision_id must reference an already-inserted
-- row, is itself immutable once written, and is constrained to a single successor per
-- predecessor -- so the lineage is an append-only chain. chk_plan_revisions_no_self_supersede
-- closes the degenerate one-row case.
--
-- STORAGE PROHIBITION (AT-D03 R8 / INV-04, restated by AT-D14 section 4 for every M3 slice): no
-- column below holds hidden reasoning, a scratchpad, a system/raw prompt, an unredacted provider
-- payload or a credential. `plan` and `diff` are structured business content and are additionally
-- key-screened in Python by shared/sdk/agent_team/models.py::assert_content_is_safe before they
-- ever reach these columns.
--
-- SAFETY: schema only. Starts no container, dispatches nothing, executes nothing, calls no
-- external provider. Idempotent / re-runnable; a matching *_down.sql reverses it.

BEGIN;

-- ---------------------------------------------------------------------
-- 1. goals -- the human/system intent the team serves (contract section 2).
--    A Goal is intent; a Work Item is work. This table never becomes a second
--    Project/WorkItem hierarchy: it hangs off the existing projects table and owns no work.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS goals (
    goal_id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id           UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    -- What outcome is wanted, in the requester's words.
    statement            TEXT NOT NULL,
    -- How the requester will know it was achieved. A JSON array of strings.
    acceptance_criteria  JSONB NOT NULL DEFAULT '[]'::jsonb,
    -- What the team must not do (scope, technology, safety, budget). A JSON array of strings.
    constraints          JSONB NOT NULL DEFAULT '[]'::jsonb,
    -- The principal that expressed the intent. NOT NULL: an intent nobody owns is not auditable.
    created_by           UUID NOT NULL REFERENCES actor_principals(principal_id),
    status               TEXT NOT NULL DEFAULT 'draft',
    audit_ref            TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_goals_statement CHECK (length(btrim(statement)) > 0),
    CONSTRAINT chk_goals_status CHECK (status IN (
        'draft', 'active', 'achieved', 'abandoned'
    )),
    CONSTRAINT chk_goals_acceptance_criteria CHECK (jsonb_typeof(acceptance_criteria) = 'array'),
    CONSTRAINT chk_goals_constraints CHECK (jsonb_typeof(constraints) = 'array'),
    -- Referenced by the composite FK on plan_revisions, so a revision can never claim a goal
    -- that belongs to a different project.
    CONSTRAINT uq_goals_id_project UNIQUE (goal_id, project_id)
);

CREATE INDEX IF NOT EXISTS idx_goals_project ON goals (project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_goals_status ON goals (status, created_at);

-- ---------------------------------------------------------------------
-- 2. plan_revisions -- versioned, historically immutable, supersedable, diffable, traceable.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS plan_revisions (
    plan_revision_id       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id             UUID NOT NULL,
    goal_id                UUID NOT NULL,
    -- Monotonic per PROJECT (contract section 3). Uniqueness is enforced below.
    revision_number        INT NOT NULL,
    created_by             UUID NOT NULL REFERENCES actor_principals(principal_id),
    -- Why this revision exists (contract section 5). 'initial' is reserved for a root revision.
    reason                 TEXT NOT NULL,
    -- NULL only for a root revision. Immutable once written.
    supersedes_revision_id UUID,
    -- The authored lifecycle status. 'superseded' is deliberately absent -- it is derived from
    -- lineage (see the header note), never written.
    status                 TEXT NOT NULL DEFAULT 'draft',
    -- The structured plan (objective / ordered, dependency-aware steps / capability requirements
    -- / expected outputs / constraints / delegation intent). Never a prose blob: M3.5 has to
    -- dispatch from this, and M3.4 has to generate work items from it.
    plan                   JSONB NOT NULL,
    -- The structured change set from the predecessor. '{}' for a root revision, which has none.
    -- Plan-state changes only -- never model reasoning about why (contract section 6's
    -- `rationale` is a human-authored conclusion, carried in the plan/diff payload, not a trace).
    diff                   JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- TRACEABLE (D04-R3): a reference to the discussion, decision or debug evidence that caused
    -- this revision. A reference, not the evidence itself, and not a foreign key -- the M3.3/M3.4
    -- artifacts it will point at do not all exist yet.
    trace_ref              TEXT,
    audit_ref              TEXT,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT chk_plan_revisions_reason CHECK (reason IN (
        'initial',
        'goal_changed',
        'clarification_answered',
        'team_decision',
        'debug_plan_invalid',
        'dependency_discovered',
        'scope_correction',
        'blocked_resolution'
    )),
    CONSTRAINT chk_plan_revisions_status CHECK (status IN (
        'draft', 'proposed', 'accepted', 'rejected'
    )),
    CONSTRAINT chk_plan_revisions_number CHECK (revision_number >= 1),
    CONSTRAINT chk_plan_revisions_plan_object CHECK (jsonb_typeof(plan) = 'object'),
    CONSTRAINT chk_plan_revisions_diff_object CHECK (jsonb_typeof(diff) = 'object'),
    -- 'initial' means exactly "this is a root revision", in both directions. A successor may
    -- never claim to be initial, and a root may never claim another cause.
    CONSTRAINT chk_plan_revisions_initial_is_root CHECK (
        (reason = 'initial') = (supersedes_revision_id IS NULL)
    ),
    CONSTRAINT chk_plan_revisions_no_self_supersede CHECK (
        supersedes_revision_id IS NULL OR supersedes_revision_id <> plan_revision_id
    ),

    -- Monotonic per project (contract section 3).
    CONSTRAINT uq_plan_revisions_project_number UNIQUE (project_id, revision_number),
    -- Referenced by the composite self-FK below.
    CONSTRAINT uq_plan_revisions_id_goal UNIQUE (plan_revision_id, goal_id),

    -- The goal must genuinely belong to the project this revision claims.
    CONSTRAINT fk_plan_revisions_goal_project
        FOREIGN KEY (goal_id, project_id) REFERENCES goals (goal_id, project_id)
        ON DELETE CASCADE,
    -- The predecessor must exist AND belong to the SAME goal. A cross-goal predecessor is not
    -- rejected by a check -- it is unrepresentable.
    CONSTRAINT fk_plan_revisions_supersedes_same_goal
        FOREIGN KEY (supersedes_revision_id, goal_id)
        REFERENCES plan_revisions (plan_revision_id, goal_id)
);

-- STALE-PLAN PROTECTION. At most one successor may ever name a given predecessor, so two
-- concurrent callers deriving from the same current revision cannot both succeed.
CREATE UNIQUE INDEX IF NOT EXISTS uq_plan_revisions_one_successor
    ON plan_revisions (supersedes_revision_id)
    WHERE supersedes_revision_id IS NOT NULL;

-- At most one ROOT revision per goal, so "the current revision" is always a single chain tip
-- rather than a forest.
CREATE UNIQUE INDEX IF NOT EXISTS uq_plan_revisions_one_root_per_goal
    ON plan_revisions (goal_id)
    WHERE supersedes_revision_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_plan_revisions_goal
    ON plan_revisions (goal_id, revision_number);
CREATE INDEX IF NOT EXISTS idx_plan_revisions_project
    ON plan_revisions (project_id, revision_number);

-- ---------------------------------------------------------------------
-- 3. Immutability, enforced by the database.
--    A revision's plan-bearing and lineage-bearing columns may never be updated in place. This
--    is what makes "a change is a NEW revision" true for every caller, including one holding a
--    raw psql session.
--
--    TWO writes are permitted, and only two. Both are narrow, both are one-way, and neither
--    touches plan content:
--
--    1. audit_ref, NULL -> value, once. Bookkeeping written when the audit sink returns.
--
--    2. status, 'draft' -> 'accepted', and nothing else. This is the team-acceptance stage the
--       approved architecture requires on the SAME revision -- planning-and-plan-revision-model.md
--       section 4 ("PlanRevision (draft) ... team acceptance ... PlanRevision (accepted)", and
--       "the team records a TeamDecision accepting THE REVISION"), and
--       source-of-truth-and-lineage-model.md, which states a PlanRevision is "immutable once
--       accepted". Immutability begins at acceptance; a blanket freeze from creation made that
--       stage unreachable and is what AT-M3.2 Validation 1 rejected as D1.
--
--       No other transition is authorized anywhere in the approved architecture, so no other
--       transition is permitted here: 'accepted' is terminal, and 'proposed'/'rejected' remain
--       creation-time values with no authorized transition until a slice's own contract adds one.
--       Plan content stays immutable in BOTH states -- stricter than "immutable once accepted",
--       deliberately, because a draft whose plan can be rewritten is not a revision.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION plan_revisions_enforce_lifecycle() RETURNS TRIGGER AS $$
BEGIN
    -- (a) Plan-bearing and lineage-bearing content: immutable in every status, forever.
    IF NEW.plan_revision_id       IS DISTINCT FROM OLD.plan_revision_id
    OR NEW.project_id             IS DISTINCT FROM OLD.project_id
    OR NEW.goal_id                IS DISTINCT FROM OLD.goal_id
    OR NEW.revision_number        IS DISTINCT FROM OLD.revision_number
    OR NEW.created_by             IS DISTINCT FROM OLD.created_by
    OR NEW.reason                 IS DISTINCT FROM OLD.reason
    OR NEW.supersedes_revision_id IS DISTINCT FROM OLD.supersedes_revision_id
    OR NEW.plan                   IS DISTINCT FROM OLD.plan
    OR NEW.diff                   IS DISTINCT FROM OLD.diff
    OR NEW.trace_ref              IS DISTINCT FROM OLD.trace_ref
    OR NEW.created_at             IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION
            'plan_revisions is append-only: revision % may not have its plan or lineage '
            'updated in place; create a successor revision instead', OLD.plan_revision_id
            USING ERRCODE = 'restrict_violation';
    END IF;

    -- (b) audit_ref is write-once: NULL -> value, never value -> anything.
    IF NEW.audit_ref IS DISTINCT FROM OLD.audit_ref AND OLD.audit_ref IS NOT NULL THEN
        RAISE EXCEPTION
            'plan_revisions.audit_ref is write-once: revision % already carries one',
            OLD.plan_revision_id
            USING ERRCODE = 'restrict_violation';
    END IF;

    -- (c) status: exactly one authorized transition. Everything else -- including
    --     accepted -> draft, accepted -> rejected, draft -> proposed, and any value the CHECK
    --     constraint would otherwise still admit -- fails closed here.
    IF NEW.status IS DISTINCT FROM OLD.status
       AND NOT (OLD.status = 'draft' AND NEW.status = 'accepted') THEN
        RAISE EXCEPTION
            'plan_revisions: % -> % is not an authorized lifecycle transition for revision %; '
            'the only permitted transition is draft -> accepted',
            OLD.status, NEW.status, OLD.plan_revision_id
            USING ERRCODE = 'restrict_violation';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Order matters on a database that already ran the earlier 038 candidate: the trigger there
-- still points at the old function, and PostgreSQL refuses to drop a function a trigger depends
-- on. Drop the trigger first, then the superseded function, then rebind the trigger. A fresh
-- database reaches the same end state through the same statements.
DROP TRIGGER IF EXISTS trg_plan_revisions_immutable ON plan_revisions;

-- The pre-remediation function froze status outright, which made the approved acceptance stage
-- unreachable. Dropped by name so no orphaned, now-wrong function is left behind.
DROP FUNCTION IF EXISTS plan_revisions_reject_update();

CREATE TRIGGER trg_plan_revisions_immutable
    BEFORE UPDATE ON plan_revisions
    FOR EACH ROW EXECUTE FUNCTION plan_revisions_enforce_lifecycle();

-- No DELETE trigger is added. Deleting a revision is already prevented for any revision that has
-- a successor (the self-FK), and cascade-on-project-delete must keep working; a blanket DELETE
-- ban would break project teardown without protecting anything a replan can reach.

-- ---------------------------------------------------------------------
-- 4. The one authorized alteration of an AT-M2 table (AT-D14).
--    team_decisions.resulting_plan_revision_id was created as bare TEXT in migration 036 because
--    plan_revisions did not exist yet. It becomes a real UUID foreign key now, exactly as AT-D14
--    pre-cleared and no further.
--
--    A TeamDecision remains a team coordination artifact, never a substitute for a human Approval
--    or ProductOwnerDecision (AT-ADR-06 / INV-03, restated in AT-D14 section 4). This migration
--    changes the column's TYPE and adds referential integrity; it changes no decision semantics
--    and touches no approval table.
--
--    Conversion safety: no writer has ever populated this column (TeamStore.record_decision does
--    not name it in its INSERT), so every existing row holds NULL. The USING clause below is
--    still written defensively -- blank/whitespace text becomes NULL rather than failing the
--    migration, and any genuinely non-UUID value would surface as a loud cast error rather than
--    being silently discarded.
-- ---------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'team_decisions'
          AND column_name = 'resulting_plan_revision_id'
          AND data_type <> 'uuid'
    ) THEN
        ALTER TABLE team_decisions
            ALTER COLUMN resulting_plan_revision_id TYPE UUID
            USING NULLIF(btrim(resulting_plan_revision_id), '')::uuid;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_name = 'team_decisions'
          AND constraint_type = 'FOREIGN KEY'
          AND constraint_name = 'fk_team_decisions_resulting_plan_revision'
    ) THEN
        ALTER TABLE team_decisions
            ADD CONSTRAINT fk_team_decisions_resulting_plan_revision
            FOREIGN KEY (resulting_plan_revision_id)
            REFERENCES plan_revisions (plan_revision_id)
            ON DELETE SET NULL;
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_team_decisions_resulting_plan_revision
    ON team_decisions (resulting_plan_revision_id);

COMMIT;
