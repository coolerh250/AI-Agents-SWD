-- 020_mini_project_delivery_pilot.sql
-- Stage 48 -- Mini Project Delivery Pilot (Step 46).
--
-- Strictly additive + idempotent. Chains the Stage 45 project planner (017),
-- Stage 46 design review (018), and Stage 47 controlled workspace operator
-- (008 extended + 019) into one controlled end-to-end pilot, persisting
-- pilot-level evidence (steps, acceptance evaluations, QA/safety evidence,
-- delivery report, artifact refs).
--
-- Seven tables. No chain_of_thought / raw_prompt / transcript columns; only
-- summaries, evidence refs, and counts are persisted. Controlled-only: no real
-- PR, no GitHub write, no deploy, no real LLM; production_executed default
-- false everywhere. PostgreSQL 16; UUID PKs via uuid_generate_v4 (001).
--
-- NOTE: code_workspaces' PK is ``workspace_id`` (Stage 28), so workspace FKs
-- reference code_workspaces(workspace_id).

BEGIN;

-- ---------------------------------------------------------------------
-- 1. mini_delivery_pilots -- one end-to-end pilot run.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mini_delivery_pilots (
    id                        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id                UUID REFERENCES projects(id) ON DELETE CASCADE,
    source_task_id            UUID,
    workspace_id              UUID REFERENCES code_workspaces(workspace_id) ON DELETE SET NULL,
    design_review_session_id  UUID REFERENCES design_review_sessions(id) ON DELETE SET NULL,
    graph_snapshot_id         UUID REFERENCES project_graph_snapshots(id) ON DELETE SET NULL,
    pilot_key                 TEXT NOT NULL UNIQUE,
    pilot_type                TEXT NOT NULL DEFAULT 'fastapi_todo_service',
    status                    TEXT NOT NULL DEFAULT 'created',
    controlled_only           BOOLEAN NOT NULL DEFAULT true,
    real_llm_enabled          BOOLEAN NOT NULL DEFAULT false,
    github_write_enabled      BOOLEAN NOT NULL DEFAULT false,
    pr_creation_enabled       BOOLEAN NOT NULL DEFAULT false,
    deployment_enabled        BOOLEAN NOT NULL DEFAULT false,
    production_executed        BOOLEAN NOT NULL DEFAULT false,
    created_by_agent          TEXT,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at              TIMESTAMPTZ,
    metadata                  JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_mdp_pilot_type CHECK (pilot_type IN (
        'fastapi_todo_service', 'custom_controlled_project'
    )),
    CONSTRAINT chk_mdp_status CHECK (status IN (
        'created', 'planning', 'planned', 'design_reviewing', 'design_reviewed',
        'workspace_executing', 'workspace_completed', 'qa_evaluating',
        'acceptance_evaluating', 'safety_evaluating', 'report_ready',
        'completed', 'failed', 'cancelled'
    ))
);

CREATE INDEX IF NOT EXISTS idx_mdp_project_status
    ON mini_delivery_pilots (project_id, status);
CREATE INDEX IF NOT EXISTS idx_mdp_pilot_key
    ON mini_delivery_pilots (pilot_key);

-- ---------------------------------------------------------------------
-- 2. mini_delivery_pilot_steps -- per-stage execution result.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mini_delivery_pilot_steps (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pilot_id      UUID NOT NULL REFERENCES mini_delivery_pilots(id) ON DELETE CASCADE,
    project_id    UUID REFERENCES projects(id) ON DELETE SET NULL,
    step_key      TEXT NOT NULL,
    step_type     TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending',
    started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at  TIMESTAMPTZ,
    evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    summary       TEXT,
    metadata      JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_mdps_step_type CHECK (step_type IN (
        'planning', 'review', 'implementation', 'testing', 'qa',
        'acceptance', 'safety', 'reporting'
    )),
    CONSTRAINT chk_mdps_status CHECK (status IN (
        'pending', 'running', 'passed', 'passed_with_findings', 'failed',
        'skipped', 'blocked'
    ))
);

CREATE INDEX IF NOT EXISTS idx_mdps_pilot_step
    ON mini_delivery_pilot_steps (pilot_id, step_key);

-- ---------------------------------------------------------------------
-- 3. acceptance_evaluations -- evidence-based acceptance evaluation.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS acceptance_evaluations (
    id                       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pilot_id                 UUID NOT NULL REFERENCES mini_delivery_pilots(id) ON DELETE CASCADE,
    project_id               UUID REFERENCES projects(id) ON DELETE CASCADE,
    acceptance_criterion_id  UUID REFERENCES project_acceptance_criteria(id) ON DELETE SET NULL,
    work_item_id             UUID REFERENCES project_work_items(id) ON DELETE SET NULL,
    evaluation_status        TEXT NOT NULL DEFAULT 'pending',
    evidence_type            TEXT NOT NULL,
    evidence_ref             JSONB NOT NULL DEFAULT '{}'::jsonb,
    evaluator                TEXT,
    rationale_summary        TEXT,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata                 JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_ae_evaluation_status CHECK (evaluation_status IN (
        'satisfied', 'failed', 'pending', 'waived', 'not_applicable'
    )),
    CONSTRAINT chk_ae_evidence_type CHECK (evidence_type IN (
        'test_run', 'static_check', 'generated_file', 'workspace_artifact',
        'manual_review_required', 'documentation_review'
    )),
    CONSTRAINT uq_ae_pilot_criterion UNIQUE (pilot_id, acceptance_criterion_id)
);

CREATE INDEX IF NOT EXISTS idx_ae_pilot_status
    ON acceptance_evaluations (pilot_id, evaluation_status);
CREATE INDEX IF NOT EXISTS idx_ae_project_criterion
    ON acceptance_evaluations (project_id, acceptance_criterion_id);

-- ---------------------------------------------------------------------
-- 4. qa_evidence_reports -- QA evidence summary.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS qa_evidence_reports (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pilot_id             UUID NOT NULL REFERENCES mini_delivery_pilots(id) ON DELETE CASCADE,
    project_id           UUID REFERENCES projects(id) ON DELETE CASCADE,
    workspace_id         UUID REFERENCES code_workspaces(workspace_id) ON DELETE SET NULL,
    status               TEXT NOT NULL,
    tests_total          INTEGER,
    tests_passed         INTEGER,
    tests_failed         INTEGER,
    static_checks_status TEXT,
    coverage_summary     JSONB NOT NULL DEFAULT '{}'::jsonb,
    findings             JSONB NOT NULL DEFAULT '[]'::jsonb,
    report_summary       TEXT,
    created_by_agent     TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata             JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_qer_status CHECK (status IN (
        'passed', 'passed_with_findings', 'failed', 'blocked'
    ))
);

CREATE INDEX IF NOT EXISTS idx_qer_pilot_status
    ON qa_evidence_reports (pilot_id, status);

-- ---------------------------------------------------------------------
-- 5. safety_evidence_reports -- safety / governance evidence.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS safety_evidence_reports (
    id                                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pilot_id                          UUID NOT NULL REFERENCES mini_delivery_pilots(id) ON DELETE CASCADE,
    project_id                        UUID REFERENCES projects(id) ON DELETE CASCADE,
    workspace_id                      UUID REFERENCES code_workspaces(workspace_id) ON DELETE SET NULL,
    status                            TEXT NOT NULL,
    production_executed_count         INTEGER NOT NULL DEFAULT 0,
    github_write_performed            BOOLEAN NOT NULL DEFAULT false,
    pr_created                        BOOLEAN NOT NULL DEFAULT false,
    deployment_performed              BOOLEAN NOT NULL DEFAULT false,
    real_llm_used                     BOOLEAN NOT NULL DEFAULT false,
    real_external_delivery_performed  BOOLEAN NOT NULL DEFAULT false,
    repo_root_modified                BOOLEAN NOT NULL DEFAULT false,
    secret_leak_detected              BOOLEAN NOT NULL DEFAULT false,
    chain_of_thought_persisted        BOOLEAN NOT NULL DEFAULT false,
    findings                          JSONB NOT NULL DEFAULT '[]'::jsonb,
    report_summary                    TEXT,
    created_by_agent                  TEXT,
    created_at                        TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata                          JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_ser_status CHECK (status IN (
        'safe', 'safe_with_findings', 'blocked', 'failed'
    ))
);

CREATE INDEX IF NOT EXISTS idx_ser_pilot_status
    ON safety_evidence_reports (pilot_id, status);

-- ---------------------------------------------------------------------
-- 6. mini_delivery_reports -- pilot-level delivery report summary.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mini_delivery_reports (
    id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pilot_id              UUID NOT NULL REFERENCES mini_delivery_pilots(id) ON DELETE CASCADE,
    project_id            UUID REFERENCES projects(id) ON DELETE CASCADE,
    workspace_id          UUID REFERENCES code_workspaces(workspace_id) ON DELETE SET NULL,
    report_type           TEXT NOT NULL DEFAULT 'mini_delivery_pilot_report',
    status                TEXT NOT NULL DEFAULT 'draft',
    title                 TEXT,
    executive_summary     TEXT,
    project_summary       JSONB NOT NULL DEFAULT '{}'::jsonb,
    design_review_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    workspace_summary     JSONB NOT NULL DEFAULT '{}'::jsonb,
    qa_summary            JSONB NOT NULL DEFAULT '{}'::jsonb,
    acceptance_summary    JSONB NOT NULL DEFAULT '{}'::jsonb,
    safety_summary        JSONB NOT NULL DEFAULT '{}'::jsonb,
    known_limitations     JSONB NOT NULL DEFAULT '[]'::jsonb,
    next_steps            JSONB NOT NULL DEFAULT '[]'::jsonb,
    artifact_refs         JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_by_agent      TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata              JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_mdr_report_type CHECK (report_type IN (
        'mini_delivery_pilot_report', 'operator_summary'
    )),
    CONSTRAINT chk_mdr_status CHECK (status IN ('draft', 'ready', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_mdr_pilot_status
    ON mini_delivery_reports (pilot_id, status);

-- ---------------------------------------------------------------------
-- 7. pilot_artifacts -- pilot-level artifact references.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pilot_artifacts (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pilot_id          UUID NOT NULL REFERENCES mini_delivery_pilots(id) ON DELETE CASCADE,
    project_id        UUID REFERENCES projects(id) ON DELETE CASCADE,
    artifact_type     TEXT NOT NULL,
    title             TEXT,
    content           JSONB,
    uri               TEXT,
    created_by_agent  TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata          JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_pa_pilot_type
    ON pilot_artifacts (pilot_id, artifact_type);

COMMIT;
