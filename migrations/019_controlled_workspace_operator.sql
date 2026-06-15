-- 019_controlled_workspace_operator.sql
-- Stage 47 -- Real Repo Workspace Operator v1.
--
-- Strictly additive + idempotent. Builds on the Stage 28 controlled code
-- generation workspace (008) and the Stage 45/46 project planner + design
-- review tables (017/018).
--
-- IMPORTANT: the ``code_workspaces`` table ALREADY EXISTS (Stage 28, used by
-- the development-agent). We DO NOT redefine it -- we EXTEND it additively
-- with the Stage 47 controlled-operator columns (all nullable / defaulted so
-- existing Stage 28 rows stay valid). The Stage 28 PK is ``workspace_id`` and
-- ``task_id TEXT NOT NULL UNIQUE`` is preserved; the operator sets
-- ``task_id = workspace_key``.
--
-- Six new tables describe one controlled workspace execution:
--   workspace_files          -- file metadata (no large blobs; hash/summary)
--   workspace_operations     -- operator step log
--   workspace_test_runs      -- pytest / ruff / compileall results
--   workspace_diff_summaries -- generated-files diff summary
--   workspace_artifacts      -- workspace-level artifact references
--   work_item_execution_links-- project_work_items <-> workspace execution
--
-- review-only / controlled-only: no repo main write, no GitHub PR, no merge,
-- no deploy, no real LLM. ``production_executed`` defaults false everywhere.
-- PostgreSQL 16 compatible. UUID PKs use uuid_generate_v4() (uuid-ossp, 001).

BEGIN;

-- ---------------------------------------------------------------------
-- 0. Extend the existing Stage 28 code_workspaces table (additive).
-- ---------------------------------------------------------------------
ALTER TABLE code_workspaces ADD COLUMN IF NOT EXISTS project_id UUID;
ALTER TABLE code_workspaces ADD COLUMN IF NOT EXISTS design_review_session_id UUID;
ALTER TABLE code_workspaces ADD COLUMN IF NOT EXISTS source_task_id UUID;
ALTER TABLE code_workspaces ADD COLUMN IF NOT EXISTS workspace_key TEXT;
ALTER TABLE code_workspaces ADD COLUMN IF NOT EXISTS workspace_type TEXT
    NOT NULL DEFAULT 'generated_project';
ALTER TABLE code_workspaces ADD COLUMN IF NOT EXISTS workspace_root TEXT
    NOT NULL DEFAULT '';
ALTER TABLE code_workspaces ADD COLUMN IF NOT EXISTS generation_mode TEXT
    NOT NULL DEFAULT 'deterministic_template';
ALTER TABLE code_workspaces ADD COLUMN IF NOT EXISTS repo_write_enabled BOOLEAN
    NOT NULL DEFAULT false;
ALTER TABLE code_workspaces ADD COLUMN IF NOT EXISTS github_write_enabled BOOLEAN
    NOT NULL DEFAULT false;
ALTER TABLE code_workspaces ADD COLUMN IF NOT EXISTS deployment_enabled BOOLEAN
    NOT NULL DEFAULT false;
ALTER TABLE code_workspaces ADD COLUMN IF NOT EXISTS real_llm_enabled BOOLEAN
    NOT NULL DEFAULT false;
ALTER TABLE code_workspaces ADD COLUMN IF NOT EXISTS production_executed BOOLEAN
    NOT NULL DEFAULT false;
ALTER TABLE code_workspaces ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;
ALTER TABLE code_workspaces ADD COLUMN IF NOT EXISTS metadata JSONB
    NOT NULL DEFAULT '{}'::jsonb;

-- workspace_key is unique among controlled-operator rows (Stage 28 rows leave
-- it NULL; a partial unique index ignores those).
CREATE UNIQUE INDEX IF NOT EXISTS uq_code_workspaces_workspace_key
    ON code_workspaces (workspace_key) WHERE workspace_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_code_workspaces_project_status
    ON code_workspaces (project_id, status);

-- ---------------------------------------------------------------------
-- 1. workspace_files -- file metadata (no large file blobs).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workspace_files (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id   UUID NOT NULL REFERENCES code_workspaces(workspace_id) ON DELETE CASCADE,
    project_id     UUID REFERENCES projects(id) ON DELETE SET NULL,
    relative_path  TEXT NOT NULL,
    file_type      TEXT,
    operation      TEXT NOT NULL DEFAULT 'created',
    content_hash   TEXT,
    size_bytes     INTEGER,
    summary        TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata       JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_wf_operation CHECK (operation IN (
        'created', 'modified', 'deleted', 'unchanged'
    ))
);

CREATE INDEX IF NOT EXISTS idx_workspace_files_ws_path
    ON workspace_files (workspace_id, relative_path);

-- ---------------------------------------------------------------------
-- 2. workspace_operations -- operator step log.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workspace_operations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id    UUID NOT NULL REFERENCES code_workspaces(workspace_id) ON DELETE CASCADE,
    project_id      UUID REFERENCES projects(id) ON DELETE SET NULL,
    operation_type  TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    command         TEXT,
    exit_code       INTEGER,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ,
    output_summary  TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_wo_operation_type CHECK (operation_type IN (
        'prepare_workspace', 'generate_files', 'run_tests', 'run_static_checks',
        'collect_diff', 'summarize', 'cleanup', 'failed'
    )),
    CONSTRAINT chk_wo_status CHECK (status IN (
        'pending', 'running', 'completed', 'failed', 'skipped'
    ))
);

CREATE INDEX IF NOT EXISTS idx_workspace_operations_ws_type
    ON workspace_operations (workspace_id, operation_type);

-- ---------------------------------------------------------------------
-- 3. workspace_test_runs -- pytest / ruff / compileall results.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workspace_test_runs (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id   UUID NOT NULL REFERENCES code_workspaces(workspace_id) ON DELETE CASCADE,
    project_id     UUID REFERENCES projects(id) ON DELETE SET NULL,
    test_type      TEXT NOT NULL,
    command        TEXT NOT NULL,
    status         TEXT NOT NULL,
    exit_code      INTEGER,
    tests_total    INTEGER,
    tests_passed   INTEGER,
    tests_failed   INTEGER,
    duration_ms    INTEGER,
    output_summary TEXT,
    report_path    TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata       JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_wtr_test_type CHECK (test_type IN (
        'pytest', 'ruff', 'mypy', 'static_check', 'smoke', 'compileall'
    )),
    CONSTRAINT chk_wtr_status CHECK (status IN (
        'passed', 'failed', 'skipped', 'error'
    ))
);

CREATE INDEX IF NOT EXISTS idx_workspace_test_runs_ws_type
    ON workspace_test_runs (workspace_id, test_type);

-- ---------------------------------------------------------------------
-- 4. workspace_diff_summaries -- generated-files diff summary.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workspace_diff_summaries (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id         UUID NOT NULL REFERENCES code_workspaces(workspace_id) ON DELETE CASCADE,
    project_id           UUID REFERENCES projects(id) ON DELETE SET NULL,
    changed_files_count  INTEGER NOT NULL DEFAULT 0,
    created_files_count   INTEGER NOT NULL DEFAULT 0,
    modified_files_count INTEGER NOT NULL DEFAULT 0,
    deleted_files_count  INTEGER NOT NULL DEFAULT 0,
    diff_summary         JSONB NOT NULL DEFAULT '{}'::jsonb,
    risk_summary         TEXT,
    test_summary         TEXT,
    generated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata             JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_workspace_diff_summaries_ws
    ON workspace_diff_summaries (workspace_id);

-- ---------------------------------------------------------------------
-- 5. workspace_artifacts -- workspace-level artifact references.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workspace_artifacts (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id      UUID NOT NULL REFERENCES code_workspaces(workspace_id) ON DELETE CASCADE,
    project_id        UUID REFERENCES projects(id) ON DELETE SET NULL,
    artifact_type     TEXT NOT NULL,
    title             TEXT,
    content           JSONB,
    uri               TEXT,
    created_by_agent  TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata          JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_workspace_artifacts_ws_type
    ON workspace_artifacts (workspace_id, artifact_type);

-- ---------------------------------------------------------------------
-- 6. work_item_execution_links -- project_work_items <-> workspace.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS work_item_execution_links (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id           UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    work_item_id         UUID NOT NULL REFERENCES project_work_items(id) ON DELETE CASCADE,
    workspace_id         UUID NOT NULL REFERENCES code_workspaces(workspace_id) ON DELETE CASCADE,
    execution_status     TEXT NOT NULL DEFAULT 'pending',
    evidence_artifact_id UUID REFERENCES workspace_artifacts(id) ON DELETE SET NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata             JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_wiel_status CHECK (execution_status IN (
        'pending', 'generated', 'tested', 'passed', 'failed', 'skipped'
    )),
    CONSTRAINT uq_wiel_workitem_ws UNIQUE (work_item_id, workspace_id)
);

CREATE INDEX IF NOT EXISTS idx_work_item_execution_links_proj_wi
    ON work_item_execution_links (project_id, work_item_id);

COMMIT;
