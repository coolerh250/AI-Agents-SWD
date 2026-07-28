-- Step 66C.4-BE3-R1 -- reverse the production-action approval registry.
--
-- Drops ONLY the table created by 035_be3_production_action_approvals.sql (and, with it, its
-- constraints and indexes). Touches no other table. Safe to run on a scratch database that applied
-- 035 before re-applying a corrected 035. No existing table or row is affected.

BEGIN;

DROP TABLE IF EXISTS production_action_approvals CASCADE;

COMMIT;
