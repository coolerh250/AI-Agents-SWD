-- Step 60 (Stage 62A) -- Release & Deployment Governance.
--
-- Persists release candidates, deployment intents, evidence packages, readiness
-- decisions, and audit events with project / work-item / delivery-package linkage.
-- Idempotent (CREATE TABLE IF NOT EXISTS). target_environment can NEVER be production
-- (CHECK); production_ready / production_executed default false. A row is a governance
-- artifact only: NOT a deploy, NOT a release, NOT a production approval.

-- ---- release_candidates ------------------------------------------------------
CREATE TABLE IF NOT EXISTS release_candidates (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id           UUID REFERENCES projects(id) ON DELETE SET NULL,
    version_label        TEXT NOT NULL,
    target_environment   TEXT NOT NULL DEFAULT 'nonprod'
        CHECK (target_environment IN ('dev','test','nonprod')),
    work_item_ids        JSONB NOT NULL DEFAULT '[]'::jsonb,
    delivery_package_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    sandbox_draft_pr_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    status               TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft','evidence_collecting','ready_for_operator_review',
                          'blocked','rejected','accepted_nonproduction','archived')),
    readiness_status     TEXT NOT NULL DEFAULT 'not_ready',
    security_status      TEXT NOT NULL DEFAULT 'unknown',
    runtime_status       TEXT NOT NULL DEFAULT 'unknown',
    gitops_status        TEXT NOT NULL DEFAULT 'unknown',
    approval_status      TEXT NOT NULL DEFAULT 'not_requested',
    production_ready     BOOLEAN NOT NULL DEFAULT false,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_release_candidates_project_id ON release_candidates (project_id);
CREATE INDEX IF NOT EXISTS idx_release_candidates_created_at ON release_candidates (created_at DESC);

-- ---- deployment_intents ------------------------------------------------------
CREATE TABLE IF NOT EXISTS deployment_intents (
    id                       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    release_candidate_id     UUID NOT NULL REFERENCES release_candidates(id) ON DELETE CASCADE,
    target_environment       TEXT NOT NULL DEFAULT 'nonprod'
        CHECK (target_environment IN ('dev','test','nonprod')),
    target_runtime           TEXT,
    target_gitops_application TEXT,
    requested_action         TEXT NOT NULL
        CHECK (requested_action IN ('validate_only','prepare_nonproduction',
                                    'request_operator_review')),
    status                   TEXT NOT NULL DEFAULT 'created'
        CHECK (status IN ('created','validated','blocked','operator_review_requested')),
    requires_human_approval  BOOLEAN NOT NULL DEFAULT false,
    policy_decision          TEXT NOT NULL DEFAULT 'pending',
    blocked_reason           TEXT,
    production_executed       BOOLEAN NOT NULL DEFAULT false,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_deployment_intents_candidate
    ON deployment_intents (release_candidate_id);
CREATE INDEX IF NOT EXISTS idx_deployment_intents_created_at
    ON deployment_intents (created_at DESC);

-- ---- release_evidence_packages -----------------------------------------------
CREATE TABLE IF NOT EXISTS release_evidence_packages (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    release_candidate_id UUID NOT NULL REFERENCES release_candidates(id) ON DELETE CASCADE,
    evidence             JSONB NOT NULL DEFAULT '{}'::jsonb,
    missing_required     JSONB NOT NULL DEFAULT '[]'::jsonb,
    complete             BOOLEAN NOT NULL DEFAULT false,
    production_ready      BOOLEAN NOT NULL DEFAULT false,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_release_evidence_candidate
    ON release_evidence_packages (release_candidate_id);

-- ---- release_readiness_decisions ---------------------------------------------
CREATE TABLE IF NOT EXISTS release_readiness_decisions (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    release_candidate_id UUID NOT NULL REFERENCES release_candidates(id) ON DELETE CASCADE,
    decision             TEXT NOT NULL,
    blockers             JSONB NOT NULL DEFAULT '[]'::jsonb,
    missing_evidence     JSONB NOT NULL DEFAULT '[]'::jsonb,
    production_ready      BOOLEAN NOT NULL DEFAULT false,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_release_readiness_candidate
    ON release_readiness_decisions (release_candidate_id);

-- ---- release_audit_events ----------------------------------------------------
CREATE TABLE IF NOT EXISTS release_audit_events (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    release_candidate_id UUID REFERENCES release_candidates(id) ON DELETE SET NULL,
    deployment_intent_id UUID REFERENCES deployment_intents(id) ON DELETE SET NULL,
    event_type           TEXT NOT NULL,
    actor                TEXT,
    role                 TEXT,
    target_environment   TEXT,
    policy_decision      TEXT,
    production_executed   BOOLEAN NOT NULL DEFAULT false,
    metadata             JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_release_audit_candidate
    ON release_audit_events (release_candidate_id);
