-- Step 62 (Stage 64A) -- Production Deployment Readiness Gate.
--
-- Persists readiness gates, checklists, evidence items, blocking rules, operator review
-- packages, readiness decisions, and rollout preflights. Idempotent (CREATE TABLE IF NOT
-- EXISTS). production_ready / production_approved / production_action_allowed /
-- production_executed default false. A row is a governance artifact only: NOT a deploy,
-- NOT a production approval, NOT a production action.

CREATE TABLE IF NOT EXISTS production_readiness_gates (
    id                       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    label                    TEXT,
    production_ready         BOOLEAN NOT NULL DEFAULT false,
    production_approved      BOOLEAN NOT NULL DEFAULT false,
    production_action_allowed BOOLEAN NOT NULL DEFAULT false,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS production_readiness_checklists (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category    TEXT NOT NULL,
    required    BOOLEAN NOT NULL DEFAULT true,
    status      TEXT NOT NULL DEFAULT 'unknown',
    blocking_if_missing BOOLEAN NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS readiness_evidence_items (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name             TEXT NOT NULL,
    source           TEXT,
    freshness        TEXT,
    availability     TEXT,
    production_scope BOOLEAN NOT NULL DEFAULT false,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS production_blocking_rules (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            TEXT NOT NULL,
    severity        TEXT NOT NULL DEFAULT 'hard',
    currently_active BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS operator_review_packages (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    decision_status TEXT NOT NULL,
    summary         JSONB NOT NULL DEFAULT '{}'::jsonb,
    production_ready BOOLEAN NOT NULL DEFAULT false,
    production_approved BOOLEAN NOT NULL DEFAULT false,
    production_action_allowed BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_operator_review_packages_created_at
    ON operator_review_packages (created_at DESC);

CREATE TABLE IF NOT EXISTS production_readiness_decisions (
    id                       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    decision                 TEXT NOT NULL
        CHECK (decision IN ('not_ready','blocked_by_missing_evidence','blocked_by_policy',
                            'blocked_by_production_prerequisites','ready_for_operator_review',
                            'operator_review_requested')),
    blockers                 JSONB NOT NULL DEFAULT '[]'::jsonb,
    missing_evidence         JSONB NOT NULL DEFAULT '[]'::jsonb,
    production_ready         BOOLEAN NOT NULL DEFAULT false,
    production_approved      BOOLEAN NOT NULL DEFAULT false,
    production_action_allowed BOOLEAN NOT NULL DEFAULT false,
    production_executed      BOOLEAN NOT NULL DEFAULT false,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_production_readiness_decisions_created_at
    ON production_readiness_decisions (created_at DESC);

CREATE TABLE IF NOT EXISTS production_rollout_preflights (
    id                       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    rollout_status           TEXT NOT NULL DEFAULT 'not_started',
    rollout_execution_enabled BOOLEAN NOT NULL DEFAULT false,
    checks                   JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);
