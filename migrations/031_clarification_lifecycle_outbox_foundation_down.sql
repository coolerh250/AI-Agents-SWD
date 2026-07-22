-- Step 66C.4-BE1 -- rollback for 031_clarification_lifecycle_outbox_foundation.sql.
--
-- Removes ONLY the objects that migration added: the clarification_lifecycle_outbox table
-- (and its indexes/constraints, dropped with the table), the two partial indexes on
-- operator_clarification_requests, the lifecycle-ordering CHECK constraint, and the six
-- additive lifecycle columns. It touches no pre-existing column, no pre-existing table, and
-- no data outside the BE1-added objects. Idempotent / re-runnable (IF EXISTS throughout).
--
-- Because all six lifecycle columns are nullable and were never backfilled, dropping them
-- loses no pre-existing data. This rollback is intended for isolated test PostgreSQL; BE1 is
-- not authorized for shared-runtime deployment.

BEGIN;

-- Dropping the table also drops its indexes and CHECK constraints, including the Step
-- 66C.4-BE1-R1 durability columns (available_at / dead_at / last_error) and their indexes.
DROP TABLE IF EXISTS clarification_lifecycle_outbox;

DROP INDEX IF EXISTS idx_ocr_reminder_due;
DROP INDEX IF EXISTS idx_ocr_expiry_due;

ALTER TABLE operator_clarification_requests
    DROP CONSTRAINT IF EXISTS chk_ocr_resume_authorized_requires_eligible;

ALTER TABLE operator_clarification_requests
    DROP COLUMN IF EXISTS reminder_sent_at,
    DROP COLUMN IF EXISTS expired_at,
    DROP COLUMN IF EXISTS resume_eligible_at,
    DROP COLUMN IF EXISTS resume_requested_at,
    DROP COLUMN IF EXISTS resume_requested_by,
    DROP COLUMN IF EXISTS resume_authorized_at;

COMMIT;
