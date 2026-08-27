-- Reverses 039_at_m3_3_bounded_team_discussion.sql.
--
-- Drops the three AT-M3.3 tables and their two trigger functions. Nothing in AT-M2 or AT-M3.2 is
-- touched, because the forward migration added nothing to them: conversation_threads,
-- team_messages, goals, plan_revisions and reasoning_invocations are left exactly as they were,
-- including any thread or message a discussion produced. Those are collaboration evidence and
-- outlive the orchestration record that scheduled them.
--
-- Order matters: turns and participants reference sessions, and sessions reference team_messages.
--
-- Data loss is intentional and total for the three tables below -- this is a down migration for a
-- non-production environment, not an archival step.

BEGIN;

DROP TRIGGER IF EXISTS trg_discussion_turns_append_only ON discussion_turns;
DROP TRIGGER IF EXISTS trg_discussion_sessions_terminal ON discussion_sessions;

DROP TABLE IF EXISTS discussion_turns;
DROP TABLE IF EXISTS discussion_participants;
DROP TABLE IF EXISTS discussion_sessions;

DROP FUNCTION IF EXISTS discussion_turns_enforce_append_only();
DROP FUNCTION IF EXISTS discussion_sessions_enforce_terminal();

COMMIT;
