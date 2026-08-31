-- Step AT-M3.4 -- formal planning decision: converged discussion -> TeamDecision -> accepted plan.
--
-- Implements the slice AT-D14 section 2 authorizes, narrowed by this task to the decision and
-- acceptance half: one converged AT-M3.3 discussion becomes ONE TeamDecision and ONE accepted
-- PlanRevision. Work-item decomposition and dispatch are M3.5 and have no column here.
--
-- ONE new table. It adds no column to, and changes no constraint on, any existing table -- for the
-- same reason migration 039 did not: AT-D14 pre-cleared exactly ONE alteration of an AT-M2 table
-- (the team_decisions FK migration 038 already made) and "authorizes no other alteration of an
-- AT-M2 table".
--
-- WHAT IS REUSED, NOT REBUILT:
--   team_decisions        THE formal team planning decision. This slice writes an AT-M2
--                         TeamDecision row and adds no second decision entity. planning_decisions
--                         below is a LEDGER, not a decision: it records which discussion was
--                         consumed, by which decision, producing which revision. Same relationship
--                         discussion_sessions has to conversation_threads -- orchestration over an
--                         existing entity, never a parallel copy of it.
--   plan_revisions        the draft->accepted lifecycle and the compare-and-swap stale protection
--                         AT-M3.2 already proved. No currency registry and no second lock system.
--   discussion_sessions   the AT-M3.3 convergence being consumed.
--   team_messages         the convergence-summary message that is the decision's evidence, and the
--                         proposal/challenge messages that are the deliberation behind it.
--
-- NO PROPOSAL TABLE AND NO CHALLENGE TABLE, deliberately. The approved architecture's own lineage
-- matrix (source-of-truth-and-lineage-model.md section 2) names every entity in this model, and
-- neither appears in it. collaboration-and-workroom-model.md section 6 defines propose/challenge/
-- converge as MESSAGE TYPES over ConversationThread/TeamMessage, and section 7 puts the formal
-- record in TeamDecision's own options_considered / selected_option / dissent_summary. A proposal
-- is therefore already durable and already structured: a TeamMessage of type 'proposal' plus its
-- AT-M3.3 turn-ledger entry. Creating tables for them would invent entities the architecture
-- declined to define, and would give a deliberation two competing records of what was said.
--
-- ATOMICITY is the load-bearing property, and it is a TRANSACTION, not a mechanism. The successor
-- revision, the TeamDecision, the draft->accepted transition and the ledger row below are written
-- in ONE PostgreSQL transaction by the service. There is therefore no crash window in which an
-- accepted revision exists without its decision, or a decision exists naming a revision that was
-- never accepted. No reconciliation daemon, no repair registry and no compensating workflow exist
-- here, because none is needed once the boundary is a transaction.
--
-- EXACTLY ONCE, in three independent layers, none of them a Python lock:
--   uq_planning_decisions_discussion   one formal decision per discussion, forever
--   uq_plan_revisions_one_successor    (AT-M3.2) one successor per predecessor, forever
--   uq_plan_revisions_one_root_per_goal (AT-M3.2) one root per planless Goal
-- The middle two already existed; this migration adds the first, which is what makes a retry after
-- success return the canonical decision instead of failing closed as stale.
--
-- STORAGE PROHIBITION (AT-D03 R8 / INV-04, restated by AT-D14 section 4): no column below holds a
-- prompt, a completion, hidden reasoning, a scratchpad, a token trace or a credential. The only
-- free text is an outcome label and an audit reference. The decision's business rationale lives in
-- team_decisions.rationale_summary, which the AT-M2 contract already screens.
--
-- SAFETY: schema only. Starts no container, dispatches nothing, executes nothing, calls no
-- external provider, creates no Approval. Idempotent / re-runnable; a matching *_down.sql
-- reverses it.

BEGIN;

-- ---------------------------------------------------------------------
-- 1. planning_decisions -- the finalization ledger.
--
--    Answers exactly one question no existing table can: "has this discussion already been
--    formalized, and if so into what?" Without it a retry after success reads the discussion as
--    bound to a now-superseded revision and fails closed as stale -- correct, but indistinguishable
--    from a genuine stale race, and not idempotent. With it, a retry finds its own prior result.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS planning_decisions (
    planning_decision_id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id                   UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    goal_id                      UUID NOT NULL REFERENCES goals(goal_id) ON DELETE CASCADE,

    -- The AT-M3.3 discussion consumed. UNIQUE is the exactly-once authority for this slice: one
    -- converged deliberation yields one formal planning decision, and a second attempt on the same
    -- discussion can never create a second one.
    discussion_id                UUID NOT NULL UNIQUE
                                      REFERENCES discussion_sessions(discussion_id)
                                      ON DELETE CASCADE,
    -- The exact convergence evidence the decision rests on: the discussion's result TeamMessage.
    -- Named explicitly rather than re-derived, so the decision keeps pointing at what it was made
    -- from even if the discussion is later read differently.
    result_message_id            UUID NOT NULL REFERENCES team_messages(message_id)
                                      ON DELETE CASCADE,

    -- The revision the discussion was bound to, and which the resulting revision supersedes.
    -- NULL exactly when the Goal had no plan and the resulting revision is the lineage root.
    predecessor_plan_revision_id UUID REFERENCES plan_revisions(plan_revision_id)
                                      ON DELETE CASCADE,

    -- The formal decision. An AT-M2 team_decisions row -- this column points at it, it does not
    -- replace it. UNIQUE so one TeamDecision can never be claimed by two planning decisions.
    team_decision_id             UUID NOT NULL UNIQUE REFERENCES team_decisions(decision_id)
                                      ON DELETE CASCADE,
    -- The revision the decision selected and which the same transaction accepted. UNIQUE for the
    -- same reason.
    resulting_plan_revision_id   UUID NOT NULL UNIQUE
                                      REFERENCES plan_revisions(plan_revision_id)
                                      ON DELETE CASCADE,

    outcome                      TEXT NOT NULL,
    idempotency_key              TEXT NOT NULL UNIQUE,
    audit_ref                    TEXT,
    created_at                   TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- One outcome, because the input gate admits exactly one situation. M3.4 consumes ONLY a
    -- converged discussion, and convergence is precisely "the team has something to accept". The
    -- architecture does permit a TeamDecision that changes no plan -- collaboration-and-workroom-
    -- model.md section 7 makes resulting_plan_revision_id nullable -- but no admissible M3.4 input
    -- reaches it, so no code writes it and this CHECK does not pretend otherwise. Adding an
    -- outcome later is a migration and a decision, which is the correct cost.
    CONSTRAINT chk_planning_decisions_outcome CHECK (outcome = 'plan_accepted'),
    -- A revision cannot supersede itself, and a root cannot be its own predecessor.
    CONSTRAINT chk_planning_decisions_lineage CHECK (
        predecessor_plan_revision_id IS NULL
        OR predecessor_plan_revision_id <> resulting_plan_revision_id
    ),
    CONSTRAINT chk_planning_decisions_key CHECK (length(btrim(idempotency_key)) > 0)
);

CREATE INDEX IF NOT EXISTS idx_planning_decisions_goal
    ON planning_decisions (goal_id, created_at);
CREATE INDEX IF NOT EXISTS idx_planning_decisions_project
    ON planning_decisions (project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_planning_decisions_predecessor
    ON planning_decisions (predecessor_plan_revision_id);

-- ---------------------------------------------------------------------
-- 2. A formal decision is evidence, and evidence is append-only.
--
--    Every column here names something that already happened: which discussion was consumed, what
--    it produced, and what it superseded. Rewriting any of them would rewrite the record of a
--    decision the team actually made -- the same reasoning plan_revisions applies to an accepted
--    revision and discussion_sessions applies to a terminal discussion.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION planning_decisions_enforce_append_only() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.planning_decision_id         IS DISTINCT FROM OLD.planning_decision_id
    OR NEW.project_id                   IS DISTINCT FROM OLD.project_id
    OR NEW.goal_id                      IS DISTINCT FROM OLD.goal_id
    OR NEW.discussion_id                IS DISTINCT FROM OLD.discussion_id
    OR NEW.result_message_id            IS DISTINCT FROM OLD.result_message_id
    OR NEW.predecessor_plan_revision_id IS DISTINCT FROM OLD.predecessor_plan_revision_id
    OR NEW.team_decision_id             IS DISTINCT FROM OLD.team_decision_id
    OR NEW.resulting_plan_revision_id   IS DISTINCT FROM OLD.resulting_plan_revision_id
    OR NEW.outcome                      IS DISTINCT FROM OLD.outcome
    OR NEW.idempotency_key              IS DISTINCT FROM OLD.idempotency_key
    OR NEW.created_at                   IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION
            'planning decision % is a record of a decision already made and may not be rewritten',
            OLD.planning_decision_id
            USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_planning_decisions_append_only ON planning_decisions;
CREATE TRIGGER trg_planning_decisions_append_only
    BEFORE UPDATE ON planning_decisions
    FOR EACH ROW EXECUTE FUNCTION planning_decisions_enforce_append_only();

COMMIT;
