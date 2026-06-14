-- 018_agent_discussion_design_review.sql
-- Stage 46 -- Agent Discussion & Design Review Protocol.
--
-- Strictly additive + idempotent. Builds on the Stage 45 project planner /
-- task graph tables (017). Adds structured, governable, auditable design-review
-- tables that sit BESIDE the Stage 27 ``agent_discussions`` per-task log (which
-- is NOT modified) and the Stage 45 project tables.
--
-- Eight tables:
--   agent_discussion_sessions       -- one structured discussion per project/decision
--   agent_discussion_participants   -- role participants (review output sources)
--   agent_discussion_contributions  -- role output SUMMARIES (no chain-of-thought)
--   design_review_sessions          -- formal design review
--   design_review_findings          -- review findings
--   design_review_decisions         -- decision summaries
--   project_review_gates            -- project-level gate status
--   agent_discussion_artifacts      -- discussion artifact references
--
-- NOTE: there is deliberately NO chain_of_thought column, NO raw_prompt column,
-- and NO unbounded message-transcript table. Only role output summaries,
-- findings, decisions, gates, and artifact references are persisted.
-- PostgreSQL 16 compatible. UUID PKs use uuid_generate_v4() (uuid-ossp, 001).

BEGIN;

-- ---------------------------------------------------------------------
-- 1. agent_discussion_sessions.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_discussion_sessions (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id        UUID REFERENCES projects(id) ON DELETE CASCADE,
    work_item_id      UUID REFERENCES project_work_items(id) ON DELETE SET NULL,
    source_task_id    UUID,
    session_type      TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'draft',
    review_mode       TEXT NOT NULL DEFAULT 'deterministic_template',
    planning_only     BOOLEAN NOT NULL DEFAULT true,
    created_by_agent  TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at      TIMESTAMPTZ,
    metadata          JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_ads_session_type CHECK (session_type IN (
        'project_design_review', 'requirement_review', 'architecture_review',
        'qa_strategy_review', 'security_review', 'delivery_readiness_review',
        'risk_review', 'implementation_strategy_review'
    )),
    CONSTRAINT chk_ads_status CHECK (status IN (
        'draft', 'in_progress', 'completed', 'blocked', 'failed', 'cancelled'
    )),
    CONSTRAINT chk_ads_review_mode CHECK (review_mode IN (
        'deterministic_template', 'llm_assisted_disabled', 'human_review'
    ))
);

CREATE INDEX IF NOT EXISTS idx_ads_project_status
    ON agent_discussion_sessions (project_id, status);
CREATE INDEX IF NOT EXISTS idx_ads_session_type
    ON agent_discussion_sessions (session_type);

-- ---------------------------------------------------------------------
-- 2. agent_discussion_participants.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_discussion_participants (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id          UUID NOT NULL REFERENCES agent_discussion_sessions(id) ON DELETE CASCADE,
    agent_role          TEXT NOT NULL,
    participation_type  TEXT NOT NULL DEFAULT 'reviewer',
    status              TEXT NOT NULL DEFAULT 'pending',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_adp_participation_type CHECK (participation_type IN (
        'reviewer', 'owner', 'approver', 'observer'
    )),
    CONSTRAINT chk_adp_status CHECK (status IN (
        'pending', 'completed', 'skipped', 'failed'
    ))
);

CREATE INDEX IF NOT EXISTS idx_adp_session_role
    ON agent_discussion_participants (session_id, agent_role);

-- ---------------------------------------------------------------------
-- 3. agent_discussion_contributions -- role output SUMMARIES only.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_discussion_contributions (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id           UUID NOT NULL REFERENCES agent_discussion_sessions(id) ON DELETE CASCADE,
    participant_id       UUID REFERENCES agent_discussion_participants(id) ON DELETE SET NULL,
    project_id           UUID REFERENCES projects(id) ON DELETE CASCADE,
    work_item_id         UUID REFERENCES project_work_items(id) ON DELETE SET NULL,
    agent_role           TEXT NOT NULL,
    contribution_type    TEXT NOT NULL,
    summary              TEXT NOT NULL,
    rationale_summary    TEXT,
    confidence           TEXT,
    severity             TEXT,
    related_artifact_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata             JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_adc_contribution_type CHECK (contribution_type IN (
        'requirement_question', 'scope_assessment', 'architecture_option',
        'implementation_plan', 'qa_strategy', 'security_risk', 'delivery_risk',
        'acceptance_coverage', 'blocker', 'recommendation'
    )),
    CONSTRAINT chk_adc_summary_not_empty CHECK (length(btrim(summary)) > 0),
    CONSTRAINT chk_adc_confidence CHECK (confidence IS NULL OR confidence IN (
        'low', 'medium', 'high'
    )),
    CONSTRAINT chk_adc_severity CHECK (severity IS NULL OR severity IN (
        'low', 'medium', 'high', 'critical'
    ))
);

CREATE INDEX IF NOT EXISTS idx_adc_session_role
    ON agent_discussion_contributions (session_id, agent_role);

-- ---------------------------------------------------------------------
-- 4. design_review_sessions.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS design_review_sessions (
    id                     UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    discussion_session_id  UUID REFERENCES agent_discussion_sessions(id) ON DELETE SET NULL,
    project_id             UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    graph_snapshot_id      UUID REFERENCES project_graph_snapshots(id) ON DELETE SET NULL,
    review_type            TEXT NOT NULL,
    status                 TEXT NOT NULL DEFAULT 'pending',
    decision               TEXT NOT NULL DEFAULT 'planning_only',
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at           TIMESTAMPTZ,
    metadata               JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_drs_review_type CHECK (review_type IN (
        'project_design', 'architecture', 'implementation', 'qa_strategy',
        'security', 'delivery', 'full_pre_execution'
    )),
    CONSTRAINT chk_drs_status CHECK (status IN (
        'pending', 'passed', 'passed_with_findings', 'blocked', 'failed'
    )),
    CONSTRAINT chk_drs_decision CHECK (decision IN (
        'go', 'go_with_findings', 'no_go', 'needs_clarification', 'planning_only'
    ))
);

CREATE INDEX IF NOT EXISTS idx_drs_project_status
    ON design_review_sessions (project_id, status);

-- ---------------------------------------------------------------------
-- 5. design_review_findings.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS design_review_findings (
    id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    review_session_id  UUID NOT NULL REFERENCES design_review_sessions(id) ON DELETE CASCADE,
    project_id         UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    work_item_id       UUID REFERENCES project_work_items(id) ON DELETE SET NULL,
    finding_key        TEXT,
    finding_type       TEXT NOT NULL,
    severity           TEXT NOT NULL DEFAULT 'low',
    title              TEXT NOT NULL,
    description        TEXT NOT NULL,
    recommendation     TEXT,
    status             TEXT NOT NULL DEFAULT 'open',
    created_by_agent   TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata           JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_drf_finding_type CHECK (finding_type IN (
        'requirement_gap', 'architecture_risk', 'implementation_risk', 'qa_gap',
        'security_risk', 'delivery_risk', 'dependency_issue', 'acceptance_gap',
        'scope_risk'
    )),
    CONSTRAINT chk_drf_severity CHECK (severity IN (
        'low', 'medium', 'high', 'critical'
    )),
    CONSTRAINT chk_drf_status CHECK (status IN (
        'open', 'accepted', 'mitigated', 'waived', 'closed'
    ))
);

CREATE INDEX IF NOT EXISTS idx_drf_project_sev_status
    ON design_review_findings (project_id, severity, status);

-- ---------------------------------------------------------------------
-- 6. design_review_decisions.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS design_review_decisions (
    id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    review_session_id  UUID NOT NULL REFERENCES design_review_sessions(id) ON DELETE CASCADE,
    project_id         UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    decision_type      TEXT NOT NULL,
    decision           TEXT NOT NULL,
    rationale_summary  TEXT,
    decided_by         TEXT,
    approval_required  BOOLEAN NOT NULL DEFAULT false,
    approval_status    TEXT NOT NULL DEFAULT 'not_required',
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata           JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_drd_decision_type CHECK (decision_type IN (
        'architecture_decision', 'implementation_decision', 'qa_decision',
        'security_decision', 'delivery_decision', 'clarification_decision',
        'go_no_go_decision'
    )),
    CONSTRAINT chk_drd_approval_status CHECK (approval_status IN (
        'not_required', 'pending', 'approved', 'rejected'
    ))
);

CREATE INDEX IF NOT EXISTS idx_drd_project_type
    ON design_review_decisions (project_id, decision_type);

-- ---------------------------------------------------------------------
-- 7. project_review_gates.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS project_review_gates (
    id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id         UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    gate_type          TEXT NOT NULL,
    status             TEXT NOT NULL DEFAULT 'pending',
    required           BOOLEAN NOT NULL DEFAULT true,
    blocking           BOOLEAN NOT NULL DEFAULT true,
    review_session_id  UUID REFERENCES design_review_sessions(id) ON DELETE SET NULL,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata           JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_prg_gate_type CHECK (gate_type IN (
        'requirement_gate', 'architecture_gate', 'implementation_strategy_gate',
        'qa_strategy_gate', 'security_gate', 'delivery_gate', 'pre_execution_gate'
    )),
    CONSTRAINT chk_prg_status CHECK (status IN (
        'pending', 'passed', 'passed_with_findings', 'blocked', 'failed', 'waived'
    )),
    CONSTRAINT uq_prg_project_gate UNIQUE (project_id, gate_type)
);

CREATE INDEX IF NOT EXISTS idx_prg_project_gate
    ON project_review_gates (project_id, gate_type);
CREATE INDEX IF NOT EXISTS idx_prg_project_status
    ON project_review_gates (project_id, status);

-- ---------------------------------------------------------------------
-- 8. agent_discussion_artifacts.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_discussion_artifacts (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id        UUID NOT NULL REFERENCES agent_discussion_sessions(id) ON DELETE CASCADE,
    project_id        UUID REFERENCES projects(id) ON DELETE CASCADE,
    artifact_type     TEXT NOT NULL,
    title             TEXT,
    content           JSONB,
    uri               TEXT,
    created_by_agent  TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata          JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_ada_session
    ON agent_discussion_artifacts (session_id);

COMMIT;
