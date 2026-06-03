-- 009_qa_validation_autofix.sql
-- Stage 29 — QA-guided validation + deterministic auto-fix loop.
--
-- Three new tables capture: (1) one QA validation "run" per
-- (workspace, attempt), (2) the per-finding rows the rules emit,
-- and (3) the auto-fix request rows the qa-agent files against
-- the development-agent.
--
-- Strictly additive + idempotent. Existing tables
-- (code_workspaces, code_change_artifacts, pr_draft_artifacts,
-- task_work_items, workflow_states, audit_logs, …) are untouched.

BEGIN;

-- ---------------------------------------------------------------------
-- 1. qa_validation_runs — one row per QA pass on a workspace.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS qa_validation_runs (
    qa_run_id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id                  TEXT NOT NULL,
    workflow_id              TEXT,
    workspace_id             UUID,
    pr_draft_id              UUID,
    status                   TEXT NOT NULL DEFAULT 'started',
    validation_scope         TEXT NOT NULL DEFAULT 'workspace',
    qa_agent                 TEXT NOT NULL DEFAULT 'qa-agent',
    total_findings           INTEGER NOT NULL DEFAULT 0,
    blocking_findings        INTEGER NOT NULL DEFAULT 0,
    non_blocking_findings    INTEGER NOT NULL DEFAULT 0,
    auto_fix_attempts        INTEGER NOT NULL DEFAULT 0,
    max_auto_fix_attempts    INTEGER NOT NULL DEFAULT 2,
    final_result             TEXT NOT NULL DEFAULT 'not_applicable',
    metadata                 JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at             TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_qa_validation_runs_task_id
    ON qa_validation_runs (task_id);
CREATE INDEX IF NOT EXISTS idx_qa_validation_runs_status
    ON qa_validation_runs (status);
CREATE INDEX IF NOT EXISTS idx_qa_validation_runs_final_result
    ON qa_validation_runs (final_result);
CREATE INDEX IF NOT EXISTS idx_qa_validation_runs_created_at
    ON qa_validation_runs (created_at DESC);

-- ---------------------------------------------------------------------
-- 2. qa_findings — one row per QA rule hit.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS qa_findings (
    finding_id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    qa_run_id         UUID NOT NULL,
    task_id           TEXT NOT NULL,
    workflow_id       TEXT,
    workspace_id      UUID,
    severity          TEXT NOT NULL DEFAULT 'warning',
    category          TEXT NOT NULL DEFAULT 'unknown',
    file_path         TEXT,
    title             TEXT NOT NULL DEFAULT '',
    description       TEXT NOT NULL DEFAULT '',
    recommendation    TEXT NOT NULL DEFAULT '',
    auto_fixable      BOOLEAN NOT NULL DEFAULT FALSE,
    status            TEXT NOT NULL DEFAULT 'open',
    metadata          JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at       TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_qa_findings_task_id
    ON qa_findings (task_id);
CREATE INDEX IF NOT EXISTS idx_qa_findings_qa_run_id
    ON qa_findings (qa_run_id);
CREATE INDEX IF NOT EXISTS idx_qa_findings_severity
    ON qa_findings (severity);
CREATE INDEX IF NOT EXISTS idx_qa_findings_status
    ON qa_findings (status);
CREATE INDEX IF NOT EXISTS idx_qa_findings_created_at
    ON qa_findings (created_at DESC);

-- ---------------------------------------------------------------------
-- 3. auto_fix_requests — one row per auto-fix request the qa-agent files.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS auto_fix_requests (
    fix_request_id   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id          TEXT NOT NULL,
    workflow_id      TEXT,
    workspace_id     UUID,
    qa_run_id        UUID,
    finding_ids      JSONB NOT NULL DEFAULT '[]'::jsonb,
    attempt_number   INTEGER NOT NULL DEFAULT 1,
    status           TEXT NOT NULL DEFAULT 'requested',
    requested_by     TEXT NOT NULL DEFAULT 'qa-agent',
    reason           TEXT NOT NULL DEFAULT '',
    fix_strategy     TEXT NOT NULL DEFAULT 'deterministic',
    result           JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_auto_fix_requests_task_id
    ON auto_fix_requests (task_id);
CREATE INDEX IF NOT EXISTS idx_auto_fix_requests_status
    ON auto_fix_requests (status);
CREATE INDEX IF NOT EXISTS idx_auto_fix_requests_qa_run_id
    ON auto_fix_requests (qa_run_id);
CREATE INDEX IF NOT EXISTS idx_auto_fix_requests_created_at
    ON auto_fix_requests (created_at DESC);

COMMIT;
