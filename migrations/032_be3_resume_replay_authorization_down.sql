-- Step 66C.4-BE3-A -- reverse the durable resume/replay authorization foundation.
--
-- Drops ONLY the table created by 032_be3_resume_replay_authorization.sql (and, with it, its
-- constraints and indexes). Touches no other table. Safe to run on a scratch database that applied
-- 032 before re-applying a corrected 032. No existing table or row is affected.

BEGIN;

DROP TABLE IF EXISTS resume_replay_authorizations CASCADE;

COMMIT;
