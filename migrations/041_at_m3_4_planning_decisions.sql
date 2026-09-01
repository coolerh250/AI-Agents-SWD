-- Step AT-M3.4 (rebaselined) -- formal planning decision: converged discussion -> TeamDecision
-- -> accepted plan.
--
-- Carried forward unchanged in substance from the AT-M3.4 design review, on a new lineage based
-- on canonical main -- which is why this is 041 and not 040: numbering is derived from the
-- migrations actually merged (canonical main ends at 039), and 040 in this lineage is the AT-M3.1
-- durable-reasoning-artifact migration this slice depends on.
--
-- Implements the slice AT-D14 section 2 authorizes, narrowed by this task to the decision and
-- acceptance half: one converged AT-M3.3 discussion becomes ONE TeamDecision and, when the plan
-- actually changes, ONE accepted PlanRevision. Work-item decomposition and dispatch are M3.5 and
-- have no column here.
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
--                         consumed, which candidate plan was selected, by which decision, and
--                         which revision resulted. Same relationship discussion_sessions has to
--                         conversation_threads -- orchestration over an existing entity, never a
--                         parallel copy of it.
--   plan_revisions        the draft->accepted lifecycle and the compare-and-swap stale protection
--                         AT-M3.2 already proved. No currency registry and no second lock system.
--   discussion_sessions   the AT-M3.3 convergence being consumed.
--   team_messages         the convergence-summary message that is the decision's evidence, the
--                         proposal/challenge messages that are the deliberation behind it, and --
--                         new in this remediation -- the planner's structured CANDIDATE PLAN.
--
-- THE CANDIDATE PLAN IS THE LOAD-BEARING ADDITION (AT-M3.4-PLAN-AUTHORSHIP-DECISION-DESIGN-
-- REVIEW-1). Validation 1 demonstrated that a caller could hand this slice any structurally valid
-- PlanContent and have it recorded as the plan the team selected: with two callers racing, which
-- plan became canonical was decided by commit ordering. The fix is not a check -- it is removing
-- the input. The plan is now authored by the routed planner principal through the AT-M3.1
-- `decompose_plan` verb, persisted as a `proposal` TeamMessage carrying a PlanDraftArtifact, and
-- COPIED server-side into the revision. candidate_plan_message_id below is what makes that binding
-- structural rather than procedural: the decision names the exact immutable message its plan came
-- from, by foreign key, and no prose comparison is involved anywhere.
--
-- WHY `proposal` AND NOT `replan`: collaboration-and-workroom-model.md section 5 defines `replan`
-- as state-changing -- "yes, new PlanRevision". A candidate plan may exist and never produce one:
-- the finalization may go stale, may fail, or may conclude no_change. Typing the candidate as
-- `replan` would make a durable message assert something that did not happen. It is a structured
-- planning proposal, and `proposal` is what the vocabulary already calls that.
--
-- NO PROPOSAL TABLE AND NO CHALLENGE TABLE, deliberately. The approved architecture's own lineage
-- matrix (source-of-truth-and-lineage-model.md section 2) names every entity in this model, and
-- neither appears in it. collaboration-and-workroom-model.md section 6 defines propose/challenge/
-- converge as MESSAGE TYPES over ConversationThread/TeamMessage, and section 7 puts the formal
-- record in TeamDecision's own options_considered / selected_option / dissent_summary. Creating
-- tables for them would invent entities the architecture declined to define, and would give a
-- deliberation two competing records of what was said. The candidate plan is stored the same way
-- for the same reason.
--
-- ATOMICITY is the load-bearing property, and it is a TRANSACTION, not a mechanism. The revision
-- (when one is written), the TeamDecision, the draft->accepted transition and the ledger row are
-- written in ONE PostgreSQL transaction by the service. There is therefore no crash window in
-- which an accepted revision exists without its decision, or a decision exists naming a revision
-- that was never accepted. No reconciliation daemon, no repair registry and no compensating
-- workflow exist here, because none is needed once the boundary is a transaction.
--
-- EXACTLY ONCE, in four independent layers, none of them a Python lock:
--   uq on discussion_id                 one formal decision per discussion, forever
--   uq on resulting_plan_revision_id    one decision per resulting revision, forever
--   uq_plan_revisions_one_successor     (AT-M3.2) one successor per predecessor, forever
--   uq_plan_revisions_one_root_per_goal (AT-M3.2) one root per planless Goal
-- The last two already existed. The second is what makes the "accept the current draft in place"
-- outcome safe when two discussions reach it at once, and the first is what makes a retry after
-- success return the canonical decision instead of failing closed as stale.
--
-- STORAGE PROHIBITION (AT-D03 R8 / INV-04, restated by AT-D14 section 4): no column below holds a
-- prompt, a completion, hidden reasoning, a scratchpad, a token trace or a credential. The only
-- free text is an outcome label and an audit reference. The decision's business rationale lives in
-- team_decisions.rationale_summary, which the AT-M2 contract already screens, and the plan itself
-- lives in team_messages.content, which goes through the same screen.
--
-- SAFETY: schema only. Starts no container, dispatches nothing, executes nothing, calls no
-- external provider, creates no Approval. Idempotent / re-runnable; a matching *_down.sql
-- reverses it.

BEGIN;

-- ---------------------------------------------------------------------
-- 1. planning_decisions -- the finalization ledger.
--
--    Answers two questions no existing table can: "has this discussion already been formalized,
--    and if so into what?" and "which exact candidate plan did the team's decision select?"
--    Without the first, a retry after success reads the discussion as bound to a now-superseded
--    revision and fails closed as stale -- correct, but indistinguishable from a genuine stale
--    race, and not idempotent. Without the second, the accepted plan has no provenance at all.
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

    -- THE PLAN'S PROVENANCE. The planner-authored `proposal` TeamMessage whose content is the
    -- PlanDraftArtifact this decision selected. NOT NULL for both outcomes: a decision that
    -- accepted a plan must say which one, and a decision that changed nothing must still say what
    -- it considered and declined to change.
    --
    -- NO ACTION (the default) rather than CASCADE or RESTRICT, deliberately:
    --   CASCADE  would let deleting planning EVIDENCE delete the planning DECISION that cites it,
    --            which is exactly backwards -- the ledger would lose the row proving what was
    --            decided because someone removed the message it was decided from.
    --   RESTRICT is checked row-by-row and would break the project-level cascade every other
    --            column here already participates in: deleting a project cascades to
    --            team_messages and to planning_decisions in one statement, and RESTRICT fires
    --            before the referencing row is gone. NO ACTION defers to end-of-statement, so a
    --            whole-project delete still works while an isolated message delete is refused.
    candidate_plan_message_id    UUID NOT NULL REFERENCES team_messages(message_id),

    -- The revision the discussion was bound to. NULL exactly when the Goal had no plan and the
    -- resulting revision is the lineage root. For a no_change decision this is the revision that
    -- was confirmed -- under lock, inside the deciding transaction -- to still be current.
    predecessor_plan_revision_id UUID REFERENCES plan_revisions(plan_revision_id)
                                      ON DELETE CASCADE,

    -- The formal decision. An AT-M2 team_decisions row -- this column points at it, it does not
    -- replace it. UNIQUE so one TeamDecision can never be claimed by two planning decisions.
    team_decision_id             UUID NOT NULL UNIQUE REFERENCES team_decisions(decision_id)
                                      ON DELETE CASCADE,

    -- The revision the decision selected and which the same transaction accepted.
    --
    -- NULLABLE, which is the second load-bearing change in this remediation. A team that converges
    -- on keeping the plan it already has changes nothing, and collaboration-and-workroom-model.md
    -- section 7 makes resulting_plan_revision_id nullable for exactly that decision. The previous
    -- shape could not express it and minted a superseding revision holding an identical plan --
    -- which permanently consumed the predecessor's ONE successor slot
    -- (uq_plan_revisions_one_successor) for a decision that changed nothing.
    --
    -- Still UNIQUE where present: PostgreSQL allows repeated NULLs in a unique index, so no_change
    -- rows do not collide, while two decisions can never claim the same revision. That is what
    -- makes "accept the current draft in place" safe when two discussions reach it at once.
    resulting_plan_revision_id   UUID UNIQUE
                                      REFERENCES plan_revisions(plan_revision_id)
                                      ON DELETE CASCADE,

    outcome                      TEXT NOT NULL,
    idempotency_key              TEXT NOT NULL UNIQUE,
    audit_ref                    TEXT,
    created_at                   TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Two outcomes, because the input gate admits exactly two situations and no more. M3.4
    -- consumes ONLY a converged discussion; the planner then produces one candidate plan; and the
    -- plan either differs from what the Goal already has or it does not. Nothing else is
    -- representable, and `rejected` / `deferred` / `unresolved` are absent because no approved
    -- architecture defines them. Adding one later is a migration and a decision, which is the
    -- correct cost.
    CONSTRAINT chk_planning_decisions_outcome CHECK (
        outcome IN ('plan_accepted', 'no_change')
    ),

    -- The outcome and the columns must agree. This is what stops a no_change decision from quietly
    -- naming a revision, and a plan_accepted decision from failing to.
    CONSTRAINT chk_planning_decisions_outcome_shape CHECK (
        (outcome = 'plan_accepted' AND resulting_plan_revision_id IS NOT NULL)
        OR (outcome = 'no_change'
            AND resulting_plan_revision_id IS NULL
            AND predecessor_plan_revision_id IS NOT NULL)
    ),

    CONSTRAINT chk_planning_decisions_key CHECK (length(btrim(idempotency_key)) > 0)

    -- Deliberately NOT present: a CHECK that predecessor <> resulting. It looked like an invariant
    -- and is not one. When a Goal's current revision is still `draft` and the planner's candidate
    -- matches it exactly, the right outcome is to ACCEPT THAT REVISION -- no successor, nothing
    -- superseded -- and then predecessor and resulting are correctly the same row. The real rule,
    -- that no revision may supersede itself, is enforced where it belongs, by
    -- chk_plan_revisions_no_self_supersede on plan_revisions.
);

CREATE INDEX IF NOT EXISTS idx_planning_decisions_goal
    ON planning_decisions (goal_id, created_at);
CREATE INDEX IF NOT EXISTS idx_planning_decisions_project
    ON planning_decisions (project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_planning_decisions_predecessor
    ON planning_decisions (predecessor_plan_revision_id);
CREATE INDEX IF NOT EXISTS idx_planning_decisions_candidate
    ON planning_decisions (candidate_plan_message_id);

-- ---------------------------------------------------------------------
-- 2. A formal decision is evidence, and evidence is append-only.
--
--    Every column here names something that already happened: which discussion was consumed, which
--    candidate plan was selected, what it produced, and what it superseded. Rewriting any of them
--    would rewrite the record of a decision the team actually made -- the same reasoning
--    plan_revisions applies to an accepted revision and discussion_sessions applies to a terminal
--    discussion.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION planning_decisions_enforce_append_only() RETURNS TRIGGER AS $fn$
BEGIN
    IF NEW.planning_decision_id         IS DISTINCT FROM OLD.planning_decision_id
    OR NEW.project_id                   IS DISTINCT FROM OLD.project_id
    OR NEW.goal_id                      IS DISTINCT FROM OLD.goal_id
    OR NEW.discussion_id                IS DISTINCT FROM OLD.discussion_id
    OR NEW.result_message_id            IS DISTINCT FROM OLD.result_message_id
    OR NEW.candidate_plan_message_id    IS DISTINCT FROM OLD.candidate_plan_message_id
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
$fn$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_planning_decisions_append_only ON planning_decisions;
CREATE TRIGGER trg_planning_decisions_append_only
    BEFORE UPDATE ON planning_decisions
    FOR EACH ROW EXECUTE FUNCTION planning_decisions_enforce_append_only();

COMMIT;
