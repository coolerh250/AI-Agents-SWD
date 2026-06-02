-- 008_code_generation_workspace.sql
-- Stage 28 — Controlled code generation workspace + PR draft delivery.
--
-- Three new tables capture: (1) the controlled workspace per task
-- (allowlist / denylist + lifecycle), (2) the per-file code change
-- artifact (diff + validation), and (3) the PR draft package
-- (changed_files / risk / rollback / dry-run result).
--
-- Strictly additive + idempotent. Existing tables (task_work_items,
-- agent_discussions, clarification_requests, workflow_states,
-- deployment_records, audit_logs, notification_deliveries, …) are
-- untouched.

BEGIN;

-- ---------------------------------------------------------------------
-- 1. code_workspaces — one row per controlled workspace.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS code_workspaces (
    workspace_id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id             TEXT NOT NULL,
    workflow_id         TEXT,
    work_item_id        UUID,
    execution_mode      TEXT NOT NULL DEFAULT 'simple_task',
    status              TEXT NOT NULL DEFAULT 'created',
    base_commit         TEXT NOT NULL DEFAULT '',
    branch_name         TEXT NOT NULL DEFAULT '',
    workspace_path      TEXT NOT NULL DEFAULT '',
    allowed_paths       JSONB NOT NULL DEFAULT '[]'::jsonb,
    denied_paths        JSONB NOT NULL DEFAULT '[]'::jsonb,
    generator_mode      TEXT NOT NULL DEFAULT 'deterministic_template',
    blocked_reason      TEXT NOT NULL DEFAULT '',
    created_by_agent    TEXT NOT NULL DEFAULT 'development-agent',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_code_workspaces_task_id
    ON code_workspaces (task_id);
CREATE INDEX IF NOT EXISTS idx_code_workspaces_status
    ON code_workspaces (status);
CREATE INDEX IF NOT EXISTS idx_code_workspaces_generator_mode
    ON code_workspaces (generator_mode);
CREATE INDEX IF NOT EXISTS idx_code_workspaces_created_at
    ON code_workspaces (created_at DESC);

-- ---------------------------------------------------------------------
-- 2. code_change_artifacts — one row per generated file.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS code_change_artifacts (
    artifact_id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id                    TEXT NOT NULL,
    workflow_id                TEXT,
    workspace_id               UUID NOT NULL,
    file_path                  TEXT NOT NULL,
    change_type                TEXT NOT NULL DEFAULT 'create',
    before_sha                 TEXT,
    after_sha                  TEXT,
    diff_summary               TEXT NOT NULL DEFAULT '',
    diff_text                  TEXT NOT NULL DEFAULT '',
    generated_content_preview  TEXT NOT NULL DEFAULT '',
    validation_status          TEXT NOT NULL DEFAULT 'pending',
    created_at                 TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_code_change_artifacts_task_id
    ON code_change_artifacts (task_id);
CREATE INDEX IF NOT EXISTS idx_code_change_artifacts_workspace_id
    ON code_change_artifacts (workspace_id);
CREATE INDEX IF NOT EXISTS idx_code_change_artifacts_validation
    ON code_change_artifacts (validation_status);
CREATE INDEX IF NOT EXISTS idx_code_change_artifacts_created_at
    ON code_change_artifacts (created_at DESC);

-- ---------------------------------------------------------------------
-- 3. pr_draft_artifacts — the package delivered to operators.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pr_draft_artifacts (
    pr_draft_id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id                TEXT NOT NULL,
    workflow_id            TEXT,
    workspace_id           UUID NOT NULL,
    title                  TEXT NOT NULL DEFAULT '',
    body                   TEXT NOT NULL DEFAULT '',
    changed_files          JSONB NOT NULL DEFAULT '[]'::jsonb,
    test_results           JSONB NOT NULL DEFAULT '{}'::jsonb,
    risk_assessment        JSONB NOT NULL DEFAULT '{}'::jsonb,
    rollback_plan          TEXT NOT NULL DEFAULT '',
    github_dry_run_result  JSONB NOT NULL DEFAULT '{}'::jsonb,
    status                 TEXT NOT NULL DEFAULT 'draft',
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_pr_draft_artifacts_task_id
    ON pr_draft_artifacts (task_id);
CREATE INDEX IF NOT EXISTS idx_pr_draft_artifacts_status
    ON pr_draft_artifacts (status);
CREATE INDEX IF NOT EXISTS idx_pr_draft_artifacts_created_at
    ON pr_draft_artifacts (created_at DESC);

COMMIT;
