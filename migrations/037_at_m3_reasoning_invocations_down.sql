-- Step AT-M3.1 -- reverse the reasoning-invocation metadata schema.
--
-- Drops ONLY the one table created by 037_at_m3_reasoning_invocations.sql (and, with it, its
-- constraints and indexes). Touches no other table, restores no data and affects no existing row.
-- Safe to run on a scratch database that applied 037 before re-applying a corrected 037.

BEGIN;

DROP TABLE IF EXISTS reasoning_invocations CASCADE;

COMMIT;
