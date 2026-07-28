-- Step 66C.4-BE3-C -- reverse the authorized dead-event replay request foundation.
--
-- Drops ONLY the table created by 034_be3_replay_requests.sql (and, with it, its constraints and
-- indexes). Touches no other table. Safe to run on a scratch database that applied 034 before
-- re-applying a corrected 034. No existing table or row is affected.

BEGIN;

DROP TABLE IF EXISTS replay_requests CASCADE;

COMMIT;
