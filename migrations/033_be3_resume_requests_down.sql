-- Step 66C.4-BE3-B -- reverse the operator-controlled resume request foundation.
--
-- Drops ONLY the table created by 033_be3_resume_requests.sql (and, with it, its constraints and
-- indexes). Touches no other table. Safe to run on a scratch database that applied 033 before
-- re-applying a corrected 033. No existing table or row is affected.

BEGIN;

DROP TABLE IF EXISTS resume_requests CASCADE;

COMMIT;
