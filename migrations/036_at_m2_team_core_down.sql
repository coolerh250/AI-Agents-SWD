-- Step AT-M2-TEAM-CORE -- reverse the runtime team core schema.
--
-- Drops ONLY the eight tables created by 036_at_m2_team_core.sql (and, with them, their
-- constraints and indexes), in dependency order. Touches no other table, restores no data and
-- affects no existing row. Safe to run on a scratch database that applied 036 before
-- re-applying a corrected 036.

BEGIN;

DROP TABLE IF EXISTS agent_routing_decisions CASCADE;
DROP TABLE IF EXISTS agent_handoffs CASCADE;
DROP TABLE IF EXISTS team_decisions CASCADE;
DROP TABLE IF EXISTS team_messages CASCADE;
DROP TABLE IF EXISTS conversation_threads CASCADE;
DROP TABLE IF EXISTS project_team_memberships CASCADE;
DROP TABLE IF EXISTS agent_profiles CASCADE;
DROP TABLE IF EXISTS actor_principals CASCADE;

COMMIT;
