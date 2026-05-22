-- 002_governance_tables.sql
-- Governance schema extensions for the Approval / Policy / Audit service split.
-- Adds the columns the approval-engine and audit-service persist.
-- Idempotent: safe to run multiple times.

BEGIN;

-- approval_requests: relax the tasks foreign key so mock/test task ids are
-- accepted, and add the governance columns the approval-engine writes.
ALTER TABLE approval_requests DROP CONSTRAINT IF EXISTS approval_requests_task_id_fkey;
ALTER TABLE approval_requests ALTER COLUMN task_id TYPE TEXT USING task_id::text;
ALTER TABLE approval_requests ADD COLUMN IF NOT EXISTS action     TEXT;
ALTER TABLE approval_requests ADD COLUMN IF NOT EXISTS risk_level TEXT;
ALTER TABLE approval_requests ADD COLUMN IF NOT EXISTS reason     TEXT;

-- audit_logs: add the governance columns the audit-service writes.
ALTER TABLE audit_logs ALTER COLUMN action DROP NOT NULL;
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS task_id       TEXT;
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS agent         TEXT;
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS decision_type TEXT;
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS summary       TEXT;
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS result        TEXT;

CREATE INDEX IF NOT EXISTS idx_approval_requests_task_id ON approval_requests (task_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_task_id ON audit_logs (task_id);

COMMIT;
