-- 005_incident_management.sql
-- Extend incident_records with the columns + indexes the IncidentStore SDK
-- and the orchestrator /incidents API need. Strictly additive and idempotent:
-- existing rows in incident_records are preserved.

BEGIN;

-- Correlation / routing columns. Nullable because operator-created incidents
-- need not be tied to a workflow.
ALTER TABLE incident_records ADD COLUMN IF NOT EXISTS task_id     TEXT;
ALTER TABLE incident_records ADD COLUMN IF NOT EXISTS workflow_id TEXT;

-- source identifies who/what created the incident (e.g. retry-scheduler,
-- operator). NOT NULL with a safe default so the column can be added to an
-- existing table without breaking any prior row.
ALTER TABLE incident_records ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'unknown';

-- Free-form structured payload (original event, failure_reason, retry counts).
ALTER TABLE incident_records ADD COLUMN IF NOT EXISTS details JSONB NOT NULL DEFAULT '{}'::jsonb;

-- Lifecycle timestamps.
ALTER TABLE incident_records ADD COLUMN IF NOT EXISTS acknowledged_at TIMESTAMPTZ;
ALTER TABLE incident_records ADD COLUMN IF NOT EXISTS resolved_at     TIMESTAMPTZ;

-- Indexes for the operator API filter set.
CREATE INDEX IF NOT EXISTS idx_incident_records_status      ON incident_records (status);
CREATE INDEX IF NOT EXISTS idx_incident_records_severity    ON incident_records (severity);
CREATE INDEX IF NOT EXISTS idx_incident_records_task_id     ON incident_records (task_id);
CREATE INDEX IF NOT EXISTS idx_incident_records_workflow_id ON incident_records (workflow_id);
CREATE INDEX IF NOT EXISTS idx_incident_records_created_at  ON incident_records (created_at);

COMMIT;
