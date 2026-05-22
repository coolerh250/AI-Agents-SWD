-- 003_workflow_persistence.sql
-- Workflow persistence columns for the WorkflowStore and resume engine.
-- Idempotent: safe to run multiple times.

BEGIN;

-- Relax the tasks foreign key so mock/test task ids are accepted, and make the
-- task id unique so the WorkflowStore can upsert one row per workflow.
ALTER TABLE workflow_states DROP CONSTRAINT IF EXISTS workflow_states_task_id_fkey;
ALTER TABLE workflow_states ALTER COLUMN task_id TYPE TEXT USING task_id::text;
ALTER TABLE workflow_states ALTER COLUMN phase DROP NOT NULL;

ALTER TABLE workflow_states ADD COLUMN IF NOT EXISTS stage             TEXT;
ALTER TABLE workflow_states ADD COLUMN IF NOT EXISTS request           JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE workflow_states ADD COLUMN IF NOT EXISTS approval_required BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE workflow_states ADD COLUMN IF NOT EXISTS approval_status   TEXT;
ALTER TABLE workflow_states ADD COLUMN IF NOT EXISTS risk_level        TEXT;
ALTER TABLE workflow_states ADD COLUMN IF NOT EXISTS execution_result  JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE UNIQUE INDEX IF NOT EXISTS uq_workflow_states_task_id ON workflow_states (task_id);
CREATE INDEX IF NOT EXISTS idx_workflow_states_stage ON workflow_states (stage);

COMMIT;
