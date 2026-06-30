-- Step 61 (Stage 63A) -- Backup / Restore / Disaster Recovery operations.
--
-- Persists controlled cleanup reviews, restore plans, restore validations, DR operations,
-- recovery evidence packages, and backup target / artifact governance snapshots.
-- Idempotent (CREATE TABLE IF NOT EXISTS). target_environment can NEVER be production
-- (CHECK); a DR operation_type can never be a production failover / restore / cross-region
-- failover (CHECK); production_restore / production_failover / production_executed default
-- false. A row is a governance artifact only: NOT a restore, NOT a failover, NOT a cleanup
-- execution. Does NOT collide with the Stage 51 backup_dr_gap_closure (022) tables.

-- ---- backup_targets ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS backup_targets (
    id                         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                       TEXT NOT NULL,
    source                     TEXT NOT NULL,
    classification             TEXT NOT NULL,
    contains_secret            BOOLEAN NOT NULL DEFAULT false,
    contains_customer_data     BOOLEAN NOT NULL DEFAULT false,
    backup_allowed             BOOLEAN NOT NULL DEFAULT false,
    restore_allowed_nonprod    BOOLEAN NOT NULL DEFAULT false,
    restore_allowed_production BOOLEAN NOT NULL DEFAULT false,
    retention_class            TEXT,
    cleanup_allowed            BOOLEAN NOT NULL DEFAULT false,
    created_at                 TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---- backup_artifacts --------------------------------------------------------
CREATE TABLE IF NOT EXISTS backup_artifacts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    classification  TEXT NOT NULL,
    retention_days  INTEGER NOT NULL DEFAULT 0,
    cleanup_allowed BOOLEAN NOT NULL DEFAULT false,
    commit_allowed  BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---- cleanup_reviews ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS cleanup_reviews (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    scope                   TEXT NOT NULL,
    candidates              JSONB NOT NULL DEFAULT '[]'::jsonb,
    allowed_count           INTEGER NOT NULL DEFAULT 0,
    blocked_count           INTEGER NOT NULL DEFAULT 0,
    requires_approval_count INTEGER NOT NULL DEFAULT 0,
    risk_level              TEXT NOT NULL DEFAULT 'low',
    cleanup_executed        BOOLEAN NOT NULL DEFAULT false,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_cleanup_reviews_created_at ON cleanup_reviews (created_at DESC);

-- ---- restore_plans -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS restore_plans (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    target                  TEXT NOT NULL,
    source_artifact         TEXT,
    target_environment      TEXT NOT NULL DEFAULT 'nonprod'
        CHECK (target_environment IN ('local','dev','test','nonprod')),
    restore_type            TEXT NOT NULL
        CHECK (restore_type IN ('validate_backup','restore_nonproduction_copy',
                                'dry_run_restore','schema_validation','integrity_validation')),
    status                  TEXT NOT NULL DEFAULT 'planned'
        CHECK (status IN ('planned','validated','blocked','operator_review_requested')),
    policy_decision         TEXT NOT NULL DEFAULT 'pending',
    requires_human_approval BOOLEAN NOT NULL DEFAULT false,
    blocked_reason          TEXT,
    production_restore      BOOLEAN NOT NULL DEFAULT false,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_restore_plans_created_at ON restore_plans (created_at DESC);

-- ---- restore_validations -----------------------------------------------------
CREATE TABLE IF NOT EXISTS restore_validations (
    id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    restore_plan_id    UUID REFERENCES restore_plans(id) ON DELETE SET NULL,
    validation_types   JSONB NOT NULL DEFAULT '[]'::jsonb,
    status             TEXT NOT NULL DEFAULT 'passed'
        CHECK (status IN ('passed','failed','blocked','skipped')),
    checks             JSONB NOT NULL DEFAULT '[]'::jsonb,
    missing            JSONB NOT NULL DEFAULT '[]'::jsonb,
    production_executed BOOLEAN NOT NULL DEFAULT false,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_restore_validations_plan ON restore_validations (restore_plan_id);

-- ---- dr_operations -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS dr_operations (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    operation_type      TEXT NOT NULL
        CHECK (operation_type IN ('backup_inventory','backup_validation','restore_plan_created',
                                  'restore_validation','cleanup_review','dr_readiness_assessment')),
    target_environment  TEXT NOT NULL DEFAULT 'nonprod'
        CHECK (target_environment IN ('local','dev','test','nonprod')),
    status              TEXT NOT NULL DEFAULT 'recorded'
        CHECK (status IN ('recorded','blocked','evidence_incomplete')),
    policy_decision     TEXT NOT NULL DEFAULT 'recorded',
    blocked_reason      TEXT,
    production_restore  BOOLEAN NOT NULL DEFAULT false,
    production_failover BOOLEAN NOT NULL DEFAULT false,
    production_executed BOOLEAN NOT NULL DEFAULT false,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_dr_operations_created_at ON dr_operations (created_at DESC);

-- ---- recovery_evidence_packages ----------------------------------------------
CREATE TABLE IF NOT EXISTS recovery_evidence_packages (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    evidence                JSONB NOT NULL DEFAULT '{}'::jsonb,
    missing_required        JSONB NOT NULL DEFAULT '[]'::jsonb,
    complete                BOOLEAN NOT NULL DEFAULT false,
    production_ready        BOOLEAN NOT NULL DEFAULT false,
    production_restore_ready BOOLEAN NOT NULL DEFAULT false,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
