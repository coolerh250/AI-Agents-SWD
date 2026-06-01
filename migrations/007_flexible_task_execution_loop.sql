-- 007_flexible_task_execution_loop.sql
-- Stage 27 — Discord-driven flexible task execution loop.
--
-- Three new tables capture: (1) the operator-visible "work item" the
-- platform tracks per Discord intake, (2) the inter-agent discussion
-- log for that work item, and (3) the operator clarification round-
-- trip when the requirement-agent decides it needs more input.
--
-- Strictly additive + idempotent. Existing tables (workflow_states,
-- agent_executions, audit_logs, notification_deliveries, …) are
-- untouched.

BEGIN;

-- ---------------------------------------------------------------------
-- 1. task_work_items — one row per Discord-originated task work item.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS task_work_items (
    work_item_id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id                TEXT NOT NULL,
    workflow_id            TEXT,
    title                  TEXT NOT NULL DEFAULT '',
    description            TEXT NOT NULL DEFAULT '',
    request_type           TEXT NOT NULL DEFAULT 'unknown',
    execution_mode         TEXT NOT NULL DEFAULT 'simple_task',
    status                 TEXT NOT NULL DEFAULT 'intake_received',
    priority               TEXT NOT NULL DEFAULT 'normal',
    source                 TEXT NOT NULL DEFAULT 'discord',
    requester_id           TEXT,
    channel_id             TEXT,
    task_category          TEXT NOT NULL DEFAULT 'general',
    development_required   BOOLEAN NOT NULL DEFAULT FALSE,
    github_required        BOOLEAN NOT NULL DEFAULT FALSE,
    clarification_required BOOLEAN NOT NULL DEFAULT FALSE,
    acceptance_criteria    JSONB,
    definition_of_done     JSONB,
    execution_plan         JSONB NOT NULL DEFAULT '{}'::jsonb,
    assumptions            JSONB NOT NULL DEFAULT '[]'::jsonb,
    open_questions         JSONB NOT NULL DEFAULT '[]'::jsonb,
    risks                  JSONB NOT NULL DEFAULT '[]'::jsonb,
    scrum_enabled          BOOLEAN NOT NULL DEFAULT FALSE,
    scrum_metadata         JSONB,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_task_work_items_task_id
    ON task_work_items (task_id);
CREATE INDEX IF NOT EXISTS idx_task_work_items_status
    ON task_work_items (status);
CREATE INDEX IF NOT EXISTS idx_task_work_items_execution_mode
    ON task_work_items (execution_mode);
CREATE INDEX IF NOT EXISTS idx_task_work_items_created_at
    ON task_work_items (created_at DESC);

-- ---------------------------------------------------------------------
-- 2. agent_discussions — append-only discussion log per task.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_discussions (
    discussion_id  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id        TEXT NOT NULL,
    workflow_id    TEXT,
    agent          TEXT NOT NULL,
    role           TEXT NOT NULL DEFAULT 'analyst',
    message_type   TEXT NOT NULL DEFAULT 'analysis',
    content        TEXT NOT NULL DEFAULT '',
    confidence     NUMERIC(4,3) NOT NULL DEFAULT 0.500,
    references     JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_discussions_task_id
    ON agent_discussions (task_id);
CREATE INDEX IF NOT EXISTS idx_agent_discussions_agent
    ON agent_discussions (agent);
CREATE INDEX IF NOT EXISTS idx_agent_discussions_created_at
    ON agent_discussions (created_at DESC);

-- ---------------------------------------------------------------------
-- 3. clarification_requests — operator clarification round-trip.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS clarification_requests (
    clarification_id      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id               TEXT NOT NULL,
    workflow_id           TEXT,
    question              TEXT NOT NULL,
    requested_by_agent    TEXT NOT NULL DEFAULT 'requirement-agent',
    status                TEXT NOT NULL DEFAULT 'open',
    user_response         TEXT,
    channel_id            TEXT,
    message_id            TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    answered_at           TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_clarification_requests_task_id
    ON clarification_requests (task_id);
CREATE INDEX IF NOT EXISTS idx_clarification_requests_status
    ON clarification_requests (status);
CREATE INDEX IF NOT EXISTS idx_clarification_requests_created_at
    ON clarification_requests (created_at DESC);

COMMIT;
