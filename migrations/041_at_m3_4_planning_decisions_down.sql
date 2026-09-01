-- Reverses 041_at_m3_4_planning_decisions.sql.
--
-- Drops the one AT-M3.4 table and its trigger function. Nothing in AT-M2, AT-M3.2 or AT-M3.3 is
-- touched, because the forward migration added nothing to them: team_decisions, plan_revisions,
-- discussion_sessions, team_messages and conversation_threads are left exactly as they were.
--
-- Note what this deliberately does NOT undo: the TeamDecision rows and accepted PlanRevisions that
-- planning decisions produced stay, and so do the planner-authored candidate plan messages they
-- selected -- those are ordinary team_messages and belong to the thread, not to this ledger. They are the team's own decisions and the plans it is working
-- from, not this ledger's private bookkeeping -- the same reason 039's down migration leaves the
-- threads and messages a discussion produced. Dropping the ledger loses the ability to answer
-- "which discussion produced this plan", and nothing else.
--
-- Data loss is intentional and total for the table below -- this is a down migration for a
-- non-production environment, not an archival step.

BEGIN;

DROP TRIGGER IF EXISTS trg_planning_decisions_append_only ON planning_decisions;

DROP TABLE IF EXISTS planning_decisions;

DROP FUNCTION IF EXISTS planning_decisions_enforce_append_only();

COMMIT;
