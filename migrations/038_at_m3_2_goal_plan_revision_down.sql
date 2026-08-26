-- Reverses 038_at_m3_2_goal_plan_revision.sql.
--
-- Restores team_decisions.resulting_plan_revision_id to the bare TEXT column migration 036
-- created, then drops the two AT-M3.2 tables and the immutability trigger function. Order
-- matters: the FK must go before plan_revisions can be dropped.
--
-- Data loss is intentional and total for goals/plan_revisions -- this is a down migration for a
-- non-production environment, not an archival step.

BEGIN;

ALTER TABLE IF EXISTS team_decisions
    DROP CONSTRAINT IF EXISTS fk_team_decisions_resulting_plan_revision;

DROP INDEX IF EXISTS idx_team_decisions_resulting_plan_revision;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'team_decisions'
          AND column_name = 'resulting_plan_revision_id'
          AND data_type = 'uuid'
    ) THEN
        ALTER TABLE team_decisions
            ALTER COLUMN resulting_plan_revision_id TYPE TEXT
            USING resulting_plan_revision_id::text;
    END IF;
END
$$;

DROP TRIGGER IF EXISTS trg_plan_revisions_immutable ON plan_revisions;
DROP TABLE IF EXISTS plan_revisions;
DROP FUNCTION IF EXISTS plan_revisions_reject_update();
DROP TABLE IF EXISTS goals;

COMMIT;
