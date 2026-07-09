-- Step 66B.1 -- AI Agents Team Work task API foundation.
--
-- New product-layer "operator task" resource (operator-facing task assignment),
-- distinct from the legacy `tasks` table (001_init_core_tables.sql, vestigial,
-- unused) and from the internal pipeline `task_id` string identifiers used by
-- workflow_states / task_execution. Named `operator_tasks` to avoid collision
-- and to follow the `operator_action_requests` / `operator_identities` naming
-- family (023_admin_console_operator_actions.sql).
--
-- production_effect defaults false; no row in this table ever triggers a
-- workflow dispatch or external write from 66B.1. Idempotent / re-runnable.

BEGIN;

CREATE TABLE IF NOT EXISTS operator_tasks (
    id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title                 TEXT NOT NULL,
    description           TEXT,
    task_type             TEXT NOT NULL,
    priority              TEXT NOT NULL DEFAULT 'medium',
    status                TEXT NOT NULL DEFAULT 'draft',
    created_by            TEXT NOT NULL,
    owner                 TEXT,
    project_id            UUID,
    environment           TEXT NOT NULL DEFAULT 'test',
    production_effect     BOOLEAN NOT NULL DEFAULT false,
    requires_approval     BOOLEAN NOT NULL DEFAULT false,
    clarification_status  TEXT NOT NULL DEFAULT 'none',
    delivery_status       TEXT NOT NULL DEFAULT 'none',
    intake_planning_only  BOOLEAN NOT NULL DEFAULT false,
    correlation_id        UUID NOT NULL DEFAULT uuid_generate_v4(),
    metadata              JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_operator_tasks_title_nonempty CHECK (length(btrim(title)) > 0),
    CONSTRAINT chk_operator_tasks_task_type CHECK (task_type IN (
        'software_delivery', 'documentation', 'platform_improvement', 'research',
        'it_operations', 'security_review', 'incident_analysis',
        'data_knowledge_analysis', 'business_process_automation', 'other'
    )),
    CONSTRAINT chk_operator_tasks_priority CHECK (priority IN ('low', 'medium', 'high', 'critical')),
    CONSTRAINT chk_operator_tasks_status CHECK (status IN (
        'draft', 'submitted', 'intake_review', 'clarification_needed', 'clarification_expired',
        'approved_for_execution', 'running', 'waiting_approval', 'blocked', 'failed',
        'delivery_ready', 'changes_requested', 'qa_rerun_requested', 'accepted', 'rejected',
        'archived', 'canceled'
    )),
    -- 'production' is deliberately NOT an allowed value here (defense in depth --
    -- Step 66B.1 task records are test/staging-runtime records only).
    CONSTRAINT chk_operator_tasks_environment CHECK (environment IN ('test', 'staging'))
);

CREATE INDEX IF NOT EXISTS idx_operator_tasks_status ON operator_tasks (status);
CREATE INDEX IF NOT EXISTS idx_operator_tasks_task_type ON operator_tasks (task_type);
CREATE INDEX IF NOT EXISTS idx_operator_tasks_owner ON operator_tasks (owner);
CREATE INDEX IF NOT EXISTS idx_operator_tasks_created_by ON operator_tasks (created_by);
CREATE INDEX IF NOT EXISTS idx_operator_tasks_priority ON operator_tasks (priority);
CREATE INDEX IF NOT EXISTS idx_operator_tasks_environment ON operator_tasks (environment);

COMMIT;
