-- 036_delivery_acceptance_persistence_down.sql
-- Step 66D-BE1 -- reverse the delivery acceptance persistence foundation.
--
-- Drops ONLY the five tables created by 036_delivery_acceptance_persistence.sql (and, with them,
-- their constraints and indexes). Touches NO other table: the legacy delivery_packages family
-- (migration 021), projects / project_work_items (017) and operator_tasks (029) are untouched,
-- because 036 only referenced them and never modified them.
--
-- Dropped in reverse dependency order. Safe to run on a scratch database that applied 036 before
-- re-applying a corrected 036. No existing table or row is affected.

BEGIN;

DROP TABLE IF EXISTS acceptance_follow_up_items CASCADE;
DROP TABLE IF EXISTS product_owner_decisions CASCADE;
DROP TABLE IF EXISTS delivery_review_actions CASCADE;
DROP TABLE IF EXISTS delivery_review_tasks CASCADE;
DROP TABLE IF EXISTS delivery_submissions CASCADE;

COMMIT;
