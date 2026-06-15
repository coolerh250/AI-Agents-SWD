-- 021_delivery_package_acceptance_gate.sql
-- Stage 49 -- Delivery Package & Acceptance Gate (Step 47).
--
-- Strictly additive + idempotent. Turns the Stage 48 mini delivery pilot
-- evidence (project plan, design review, controlled workspace, test results,
-- acceptance evaluations, QA / safety evidence, mini delivery report) into a
-- formal, human-reviewable Delivery Package + Acceptance Gate.
--
-- Eight tables. No chain_of_thought / raw_prompt / transcript columns; only
-- summaries, evidence refs, checklists, and counts are persisted. Controlled-
-- only: no real PR, no GitHub write, no deploy, no real LLM, no external
-- delivery. ``production_executed`` default false everywhere. Acceptance gate
-- NEVER auto-marks human acceptance: human_acceptance_status defaults pending.
--
-- NOTE: code_workspaces' PK is ``workspace_id`` (Stage 28), so workspace FKs
-- reference code_workspaces(workspace_id). PostgreSQL 16; UUID PKs via
-- uuid_generate_v4 (001).

BEGIN;

-- ---------------------------------------------------------------------
-- 1. delivery_packages -- one formal, human-reviewable delivery package.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS delivery_packages (
    id                        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id                UUID REFERENCES projects(id) ON DELETE CASCADE,
    pilot_id                  UUID REFERENCES mini_delivery_pilots(id) ON DELETE SET NULL,
    workspace_id              UUID REFERENCES code_workspaces(workspace_id) ON DELETE SET NULL,
    design_review_session_id  UUID REFERENCES design_review_sessions(id) ON DELETE SET NULL,
    package_key               TEXT NOT NULL UNIQUE,
    package_type              TEXT NOT NULL DEFAULT 'mini_project_delivery',
    status                    TEXT NOT NULL DEFAULT 'draft',
    controlled_only           BOOLEAN NOT NULL DEFAULT true,
    human_acceptance_required BOOLEAN NOT NULL DEFAULT true,
    human_acceptance_status   TEXT NOT NULL DEFAULT 'pending',
    real_llm_enabled          BOOLEAN NOT NULL DEFAULT false,
    github_write_enabled      BOOLEAN NOT NULL DEFAULT false,
    pr_creation_enabled       BOOLEAN NOT NULL DEFAULT false,
    deployment_enabled        BOOLEAN NOT NULL DEFAULT false,
    external_delivery_enabled BOOLEAN NOT NULL DEFAULT false,
    production_executed        BOOLEAN NOT NULL DEFAULT false,
    created_by_agent          TEXT,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at              TIMESTAMPTZ,
    metadata                  JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_dp_package_type CHECK (package_type IN (
        'mini_project_delivery', 'controlled_workspace_delivery', 'formal_handoff'
    )),
    CONSTRAINT chk_dp_status CHECK (status IN (
        'draft', 'building', 'ready_for_review', 'accepted', 'rejected',
        'blocked', 'failed', 'archived'
    )),
    CONSTRAINT chk_dp_human_acceptance CHECK (human_acceptance_status IN (
        'pending', 'accepted', 'rejected', 'not_required'
    ))
);

CREATE INDEX IF NOT EXISTS idx_dp_project_status
    ON delivery_packages (project_id, status);
CREATE INDEX IF NOT EXISTS idx_dp_pilot
    ON delivery_packages (pilot_id);
CREATE INDEX IF NOT EXISTS idx_dp_package_key
    ON delivery_packages (package_key);

-- ---------------------------------------------------------------------
-- 2. delivery_package_sections -- human-readable package chapters.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS delivery_package_sections (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    package_id      UUID NOT NULL REFERENCES delivery_packages(id) ON DELETE CASCADE,
    project_id      UUID REFERENCES projects(id) ON DELETE CASCADE,
    section_key     TEXT NOT NULL,
    title           TEXT NOT NULL,
    content         JSONB NOT NULL DEFAULT '{}'::jsonb,
    content_summary TEXT,
    order_index     INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'draft',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_dps_status CHECK (status IN ('draft', 'ready', 'missing', 'failed')),
    CONSTRAINT uq_dps_package_section UNIQUE (package_id, section_key)
);

CREATE INDEX IF NOT EXISTS idx_dps_package_section
    ON delivery_package_sections (package_id, section_key);

-- ---------------------------------------------------------------------
-- 3. delivery_package_artifacts -- source artifact references.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS delivery_package_artifacts (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    package_id    UUID NOT NULL REFERENCES delivery_packages(id) ON DELETE CASCADE,
    project_id    UUID REFERENCES projects(id) ON DELETE CASCADE,
    artifact_type TEXT NOT NULL,
    source_table  TEXT,
    source_id     UUID,
    title         TEXT,
    uri           TEXT,
    content       JSONB,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata      JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_dpa_package_type
    ON delivery_package_artifacts (package_id, artifact_type);

-- ---------------------------------------------------------------------
-- 4. acceptance_gate_runs -- one acceptance-gate evaluation of a package.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS acceptance_gate_runs (
    id                       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    package_id               UUID NOT NULL REFERENCES delivery_packages(id) ON DELETE CASCADE,
    project_id               UUID REFERENCES projects(id) ON DELETE CASCADE,
    pilot_id                 UUID REFERENCES mini_delivery_pilots(id) ON DELETE SET NULL,
    gate_key                 TEXT NOT NULL UNIQUE,
    gate_type                TEXT NOT NULL DEFAULT 'mini_delivery_acceptance',
    status                   TEXT NOT NULL DEFAULT 'pending',
    decision                 TEXT NOT NULL DEFAULT 'ready_for_operator_review',
    human_review_required    BOOLEAN NOT NULL DEFAULT true,
    human_review_status      TEXT NOT NULL DEFAULT 'pending',
    blocking_findings_count  INTEGER NOT NULL DEFAULT 0,
    total_checks             INTEGER NOT NULL DEFAULT 0,
    passed_checks            INTEGER NOT NULL DEFAULT 0,
    failed_checks            INTEGER NOT NULL DEFAULT 0,
    warning_checks           INTEGER NOT NULL DEFAULT 0,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at             TIMESTAMPTZ,
    metadata                 JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_agr_gate_type CHECK (gate_type IN (
        'mini_delivery_acceptance', 'formal_delivery_acceptance', 'operator_review_gate'
    )),
    CONSTRAINT chk_agr_status CHECK (status IN (
        'pending', 'running', 'passed', 'passed_with_findings', 'blocked', 'failed'
    )),
    CONSTRAINT chk_agr_decision CHECK (decision IN (
        'ready_for_operator_review', 'accepted', 'rejected', 'blocked',
        'needs_changes', 'controlled_only_complete'
    )),
    CONSTRAINT chk_agr_human_review CHECK (human_review_status IN (
        'pending', 'accepted', 'rejected', 'not_required'
    ))
);

CREATE INDEX IF NOT EXISTS idx_agr_package_status
    ON acceptance_gate_runs (package_id, status);
CREATE INDEX IF NOT EXISTS idx_agr_gate_key
    ON acceptance_gate_runs (gate_key);

-- ---------------------------------------------------------------------
-- 5. acceptance_gate_check_results -- per-check result of an acceptance gate.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS acceptance_gate_check_results (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    gate_run_id   UUID NOT NULL REFERENCES acceptance_gate_runs(id) ON DELETE CASCADE,
    package_id    UUID REFERENCES delivery_packages(id) ON DELETE CASCADE,
    project_id    UUID REFERENCES projects(id) ON DELETE CASCADE,
    check_key     TEXT NOT NULL,
    check_type    TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending',
    severity      TEXT NOT NULL DEFAULT 'info',
    blocking      BOOLEAN NOT NULL DEFAULT false,
    evidence_ref  JSONB NOT NULL DEFAULT '{}'::jsonb,
    summary       TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata      JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_agcr_check_type CHECK (check_type IN (
        'project', 'design_review', 'workspace', 'testing', 'acceptance',
        'qa', 'safety', 'documentation', 'governance', 'human_review'
    )),
    CONSTRAINT chk_agcr_status CHECK (status IN (
        'passed', 'failed', 'warning', 'skipped', 'pending'
    )),
    CONSTRAINT chk_agcr_severity CHECK (severity IN (
        'info', 'low', 'medium', 'high', 'critical'
    )),
    CONSTRAINT uq_agcr_gate_check UNIQUE (gate_run_id, check_key)
);

CREATE INDEX IF NOT EXISTS idx_agcr_gate_check
    ON acceptance_gate_check_results (gate_run_id, check_key);
CREATE INDEX IF NOT EXISTS idx_agcr_package_status
    ON acceptance_gate_check_results (package_id, status);

-- ---------------------------------------------------------------------
-- 6. operator_acceptance_reviews -- human operator review placeholder/record.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operator_acceptance_reviews (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    package_id        UUID NOT NULL REFERENCES delivery_packages(id) ON DELETE CASCADE,
    project_id        UUID REFERENCES projects(id) ON DELETE CASCADE,
    gate_run_id       UUID REFERENCES acceptance_gate_runs(id) ON DELETE SET NULL,
    reviewer          TEXT,
    review_status     TEXT NOT NULL DEFAULT 'pending',
    review_summary    TEXT,
    requested_changes JSONB NOT NULL DEFAULT '[]'::jsonb,
    reviewed_at       TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata          JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_oar_review_status CHECK (review_status IN (
        'pending', 'accepted', 'rejected', 'changes_requested'
    ))
);

CREATE INDEX IF NOT EXISTS idx_oar_package_status
    ON operator_acceptance_reviews (package_id, review_status);

-- ---------------------------------------------------------------------
-- 7. handoff_summaries -- business / technical / operator handoff summaries.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS handoff_summaries (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    package_id       UUID NOT NULL REFERENCES delivery_packages(id) ON DELETE CASCADE,
    project_id       UUID REFERENCES projects(id) ON DELETE CASCADE,
    summary_type     TEXT NOT NULL,
    title            TEXT,
    summary          TEXT NOT NULL,
    highlights       JSONB NOT NULL DEFAULT '[]'::jsonb,
    limitations      JSONB NOT NULL DEFAULT '[]'::jsonb,
    next_steps       JSONB NOT NULL DEFAULT '[]'::jsonb,
    artifact_refs    JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_by_agent TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata         JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_hs_summary_type CHECK (summary_type IN (
        'business_summary', 'technical_summary', 'operator_summary'
    ))
);

CREATE INDEX IF NOT EXISTS idx_hs_package_type
    ON handoff_summaries (package_id, summary_type);

-- ---------------------------------------------------------------------
-- 8. delivery_readiness_snapshots -- readiness state for Admin Console v0.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS delivery_readiness_snapshots (
    id                       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    package_id               UUID NOT NULL REFERENCES delivery_packages(id) ON DELETE CASCADE,
    project_id               UUID REFERENCES projects(id) ON DELETE CASCADE,
    pilot_id                 UUID REFERENCES mini_delivery_pilots(id) ON DELETE SET NULL,
    readiness_status         TEXT NOT NULL DEFAULT 'not_ready',
    project_ready            BOOLEAN NOT NULL DEFAULT false,
    design_ready             BOOLEAN NOT NULL DEFAULT false,
    workspace_ready          BOOLEAN NOT NULL DEFAULT false,
    qa_ready                 BOOLEAN NOT NULL DEFAULT false,
    acceptance_ready         BOOLEAN NOT NULL DEFAULT false,
    safety_ready             BOOLEAN NOT NULL DEFAULT false,
    docs_ready               BOOLEAN NOT NULL DEFAULT false,
    human_acceptance_pending BOOLEAN NOT NULL DEFAULT true,
    blocking_reasons         JSONB NOT NULL DEFAULT '[]'::jsonb,
    warnings                 JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata                 JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_drs_readiness_status CHECK (readiness_status IN (
        'not_ready', 'ready_for_operator_review', 'accepted', 'blocked', 'failed'
    ))
);

CREATE INDEX IF NOT EXISTS idx_drs_project_status
    ON delivery_readiness_snapshots (project_id, readiness_status);

COMMIT;
