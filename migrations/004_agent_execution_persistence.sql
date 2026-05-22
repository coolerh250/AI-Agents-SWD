-- 004_agent_execution_persistence.sql
-- Agent execution persistence columns and mock deployment-record columns.
-- Idempotent: safe to run multiple times; does not drop or alter existing data.

BEGIN;

-- agent_executions: relax the tasks foreign key so mock/test task ids are
-- accepted, and add the columns the AgentExecutionStore writes.
ALTER TABLE agent_executions DROP CONSTRAINT IF EXISTS agent_executions_task_id_fkey;
ALTER TABLE agent_executions ALTER COLUMN task_id TYPE TEXT USING task_id::text;
ALTER TABLE agent_executions ALTER COLUMN agent_name DROP NOT NULL;
ALTER TABLE agent_executions ADD COLUMN IF NOT EXISTS agent        TEXT;
ALTER TABLE agent_executions ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;
ALTER TABLE agent_executions ADD COLUMN IF NOT EXISTS error        TEXT;
ALTER TABLE agent_executions ADD COLUMN IF NOT EXISTS metadata     JSONB NOT NULL DEFAULT '{}'::jsonb;

-- deployment_records: add task id and metadata for mock dev/test deployments.
ALTER TABLE deployment_records ADD COLUMN IF NOT EXISTS task_id  TEXT;
ALTER TABLE deployment_records ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_agent_executions_task_id ON agent_executions (task_id);
CREATE INDEX IF NOT EXISTS idx_agent_executions_agent ON agent_executions (agent);
CREATE INDEX IF NOT EXISTS idx_deployment_records_task_id ON deployment_records (task_id);

COMMIT;
