-- 023_admin_console_operator_actions.sql
-- Stage 52 -- Admin Console v1 Operator Actions (Step 50).
--
-- Strictly additive + idempotent (PostgreSQL 16). Upgrades the Admin Console
-- from read-only visibility to a CONTROLLED operator console: low-risk,
-- reversible, auditable operator actions (delivery package accept / reject /
-- request-changes, review notes, allowlisted verification rerun) gated by
-- authentication, RBAC, CSRF, policy, confirmation, idempotency, and audit.
--
-- NO raw password / raw session token / raw confirmation token / secret columns.
-- ``production_executed`` defaults false. High-risk actions (deploy, GitHub
-- write, PR, workflow mutation, production backup, policy/budget edits) are NOT
-- represented as executable here -- they remain disabled in the action catalog.

BEGIN;

-- ---------------------------------------------------------------------
-- 1. operator_identities -- who may act (test-local / oidc / service).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operator_identities (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    identity_key    TEXT NOT NULL UNIQUE,
    display_name    TEXT,
    identity_source TEXT NOT NULL DEFAULT 'test_local',
    status          TEXT NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_oi_source CHECK (identity_source IN ('test_local', 'oidc', 'service')),
    CONSTRAINT chk_oi_status CHECK (status IN ('active', 'disabled'))
);

-- ---------------------------------------------------------------------
-- 2. operator_role_assignments -- RBAC role grants.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operator_role_assignments (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    identity_id       UUID NOT NULL REFERENCES operator_identities(id) ON DELETE CASCADE,
    role              TEXT NOT NULL,
    environment_scope TEXT NOT NULL DEFAULT 'test',
    active            BOOLEAN NOT NULL DEFAULT true,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_ora_role CHECK (role IN ('viewer', 'reviewer', 'operator', 'platform_admin')),
    CONSTRAINT uq_ora UNIQUE (identity_id, role, environment_scope)
);

-- ---------------------------------------------------------------------
-- 3. admin_console_sessions -- server-side session records (no raw token).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS admin_console_sessions (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    identity_id  UUID NOT NULL REFERENCES operator_identities(id) ON DELETE CASCADE,
    session_hash TEXT NOT NULL UNIQUE,
    status       TEXT NOT NULL DEFAULT 'active',
    issued_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at   TIMESTAMPTZ NOT NULL,
    revoked_at   TIMESTAMPTZ,
    metadata     JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_acs_status CHECK (status IN ('active', 'expired', 'revoked'))
);
CREATE INDEX IF NOT EXISTS idx_acs_identity_status
    ON admin_console_sessions (identity_id, status);

-- ---------------------------------------------------------------------
-- 4. operator_action_requests -- one governed action request.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operator_action_requests (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    action_key          TEXT NOT NULL UNIQUE,
    identity_id         UUID REFERENCES operator_identities(id) ON DELETE SET NULL,
    action_type         TEXT NOT NULL,
    target_type         TEXT,
    target_id           TEXT,
    reason              TEXT NOT NULL,
    requested_payload   JSONB NOT NULL DEFAULT '{}'::jsonb,
    risk_level          TEXT NOT NULL DEFAULT 'low',
    policy_status       TEXT NOT NULL DEFAULT 'pending',
    approval_status     TEXT NOT NULL DEFAULT 'not_required',
    confirmation_status TEXT NOT NULL DEFAULT 'not_required',
    idempotency_key     TEXT NOT NULL UNIQUE,
    status              TEXT NOT NULL DEFAULT 'requested',
    requested_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at        TIMESTAMPTZ,
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_oar_reason_nonempty CHECK (length(btrim(reason)) > 0),
    CONSTRAINT chk_oar_status CHECK (status IN (
        'requested', 'policy_blocked', 'confirmation_required', 'approved',
        'executing', 'completed', 'failed', 'cancelled'
    ))
);
CREATE INDEX IF NOT EXISTS idx_oar_type_status
    ON operator_action_requests (action_type, status);
CREATE INDEX IF NOT EXISTS idx_oar_target
    ON operator_action_requests (target_type, target_id);

-- ---------------------------------------------------------------------
-- 5. operator_action_executions -- execution outcome of an action.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operator_action_executions (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    action_request_id   UUID NOT NULL REFERENCES operator_action_requests(id) ON DELETE CASCADE,
    execution_type      TEXT NOT NULL,
    status              TEXT NOT NULL,
    result_summary      TEXT,
    error_summary       TEXT,
    started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at        TIMESTAMPTZ,
    production_executed BOOLEAN NOT NULL DEFAULT false,
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_oae_request
    ON operator_action_executions (action_request_id, status);

-- ---------------------------------------------------------------------
-- 6. operator_action_confirmations -- one-time confirmation nonces (hashed).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operator_action_confirmations (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    action_request_id UUID NOT NULL REFERENCES operator_action_requests(id) ON DELETE CASCADE,
    identity_id       UUID REFERENCES operator_identities(id) ON DELETE SET NULL,
    confirmation_type TEXT NOT NULL DEFAULT 'second_confirmation',
    nonce_hash        TEXT NOT NULL,
    confirmed_at      TIMESTAMPTZ,
    expires_at        TIMESTAMPTZ NOT NULL,
    used              BOOLEAN NOT NULL DEFAULT false,
    metadata          JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_oac_request
    ON operator_action_confirmations (action_request_id);

-- ---------------------------------------------------------------------
-- 7. operator_review_notes -- operator review notes on a delivery package.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operator_review_notes (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    package_id  UUID REFERENCES delivery_packages(id) ON DELETE CASCADE,
    project_id  UUID REFERENCES projects(id) ON DELETE SET NULL,
    identity_id UUID REFERENCES operator_identities(id) ON DELETE SET NULL,
    note_type   TEXT NOT NULL DEFAULT 'general',
    summary     TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_orn_note_type CHECK (note_type IN (
        'general', 'finding', 'requested_change', 'acceptance_note', 'rejection_note'
    ))
);
CREATE INDEX IF NOT EXISTS idx_orn_package
    ON operator_review_notes (package_id, created_at);

-- ---------------------------------------------------------------------
-- 8. verification_rerun_requests -- allowlisted verification reruns.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS verification_rerun_requests (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    action_request_id UUID REFERENCES operator_action_requests(id) ON DELETE CASCADE,
    verification_key  TEXT NOT NULL,
    script_key        TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'requested',
    report_path       TEXT,
    result_marker     TEXT,
    exit_code         INTEGER,
    started_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at      TIMESTAMPTZ,
    metadata          JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_vrr_status
    ON verification_rerun_requests (verification_key, status);

-- ---------------------------------------------------------------------
-- 9. operator_action_policy_catalog -- per-action-type policy.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operator_action_policy_catalog (
    id                       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    action_type              TEXT NOT NULL UNIQUE,
    allowed_roles            JSONB NOT NULL DEFAULT '[]'::jsonb,
    risk_level               TEXT NOT NULL DEFAULT 'low',
    requires_reason          BOOLEAN NOT NULL DEFAULT true,
    requires_confirmation    BOOLEAN NOT NULL DEFAULT false,
    requires_approval_engine BOOLEAN NOT NULL DEFAULT false,
    execution_enabled        BOOLEAN NOT NULL DEFAULT false,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata                 JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- ---------------------------------------------------------------------
-- 10. operator_action_audit_links -- link an action to its audit row.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operator_action_audit_links (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    action_request_id UUID NOT NULL REFERENCES operator_action_requests(id) ON DELETE CASCADE,
    audit_log_id      UUID,
    decision_type     TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_oaal_request
    ON operator_action_audit_links (action_request_id);

COMMIT;
