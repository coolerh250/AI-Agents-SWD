-- 022_backup_dr_gap_closure.sql
-- Stage 51 -- Backup / DR Gap Closure (Step 49).
--
-- Strictly additive + idempotent. Builds a verifiable, auditable, recoverable,
-- reportable Backup / DR readiness baseline that extends the Stage 36 backup /
-- restore design (shared/sdk/backup). The goal is to advance backup readiness
-- from PASS_WITH_GAPS to PASS / PASS_WITH_NON_PRODUCTION_LIMITATIONS by closing
-- the four long-standing documented gaps:
--   encryption_no_key, storage_not_off_host, schedule_dry_run_only,
--   migration_down_gaps.
--
-- Controlled / test environment ONLY:
--   * No production backup / restore. No real cloud bucket write.
--   * No real production schedule (cron / systemd / Kubernetes CronJob).
--   * No raw key / secret / token columns. ``production_executed`` default false.
--
-- Eleven tables. PostgreSQL 16; UUID PKs via uuid_generate_v4 (001).

BEGIN;

-- ---------------------------------------------------------------------
-- 1. backup_encryption_configs -- encryption configuration metadata.
--    NO raw key / secret / token columns ever.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS backup_encryption_configs (
    id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    config_key         TEXT NOT NULL UNIQUE,
    key_source         TEXT NOT NULL,
    key_ref            TEXT,
    key_id             TEXT,
    algorithm          TEXT NOT NULL,
    status             TEXT NOT NULL,
    production_usable   BOOLEAN NOT NULL DEFAULT false,
    test_only          BOOLEAN NOT NULL DEFAULT true,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata           JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_bec_key_source CHECK (key_source IN (
        'key_file', 'mock_vault', 'env_reference', 'disabled'
    )),
    CONSTRAINT chk_bec_status CHECK (status IN (
        'configured', 'missing', 'invalid', 'disabled'
    ))
);

-- ---------------------------------------------------------------------
-- 2. backup_runs -- one backup run's metadata.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS backup_runs (
    id                         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    backup_key                 TEXT NOT NULL UNIQUE,
    environment                TEXT NOT NULL,
    source_database            TEXT NOT NULL,
    status                     TEXT NOT NULL,
    encrypted                  BOOLEAN NOT NULL DEFAULT false,
    encryption_config_id       UUID REFERENCES backup_encryption_configs(id) ON DELETE SET NULL,
    artifact_path              TEXT,
    manifest_path              TEXT,
    checksum_sha256            TEXT,
    encrypted_checksum_sha256  TEXT,
    size_bytes                 BIGINT,
    started_at                 TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at               TIMESTAMPTZ,
    production_executed        BOOLEAN NOT NULL DEFAULT false,
    metadata                   JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_br_environment CHECK (environment IN (
        'test', 'dev', 'staging', 'production'
    )),
    CONSTRAINT chk_br_status CHECK (status IN (
        'started', 'completed', 'failed', 'skipped'
    ))
);

CREATE INDEX IF NOT EXISTS idx_backup_runs_env_status
    ON backup_runs (environment, status);
CREATE INDEX IF NOT EXISTS idx_backup_runs_backup_key
    ON backup_runs (backup_key);

-- ---------------------------------------------------------------------
-- 3. backup_manifests -- backup manifest metadata.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS backup_manifests (
    id                                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    backup_run_id                      UUID REFERENCES backup_runs(id) ON DELETE CASCADE,
    manifest_version                   TEXT NOT NULL,
    source_database                    TEXT,
    schema_migration_count             INTEGER,
    table_count                        INTEGER,
    row_count_summary                  JSONB NOT NULL DEFAULT '{}'::jsonb,
    artifact_checksum_sha256           TEXT,
    encrypted_artifact_checksum_sha256 TEXT,
    encryption_key_id                  TEXT,
    encryption_algorithm               TEXT,
    created_at                         TIMESTAMPTZ NOT NULL DEFAULT now(),
    manifest_json                      JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_backup_manifests_run
    ON backup_manifests (backup_run_id);

-- ---------------------------------------------------------------------
-- 4. backup_offhost_targets -- off-host target abstraction.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS backup_offhost_targets (
    id                       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    target_key               TEXT NOT NULL UNIQUE,
    target_type              TEXT NOT NULL,
    target_uri               TEXT NOT NULL,
    status                   TEXT NOT NULL,
    real_cloud_write_enabled BOOLEAN NOT NULL DEFAULT false,
    test_only                BOOLEAN NOT NULL DEFAULT true,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata                 JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_bot_target_type CHECK (target_type IN (
        'mock_local_remote', 's3_disabled', 'gcs_disabled', 'azure_disabled'
    )),
    CONSTRAINT chk_bot_status CHECK (status IN (
        'configured', 'unavailable', 'disabled'
    ))
);

-- ---------------------------------------------------------------------
-- 5. backup_offhost_transfer_runs -- off-host copy / readback verification.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS backup_offhost_transfer_runs (
    id                       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    backup_run_id            UUID REFERENCES backup_runs(id) ON DELETE CASCADE,
    target_id                UUID REFERENCES backup_offhost_targets(id) ON DELETE SET NULL,
    status                   TEXT NOT NULL,
    source_path              TEXT,
    target_path              TEXT,
    source_checksum_sha256   TEXT,
    target_checksum_sha256   TEXT,
    readback_verified        BOOLEAN NOT NULL DEFAULT false,
    real_cloud_write_performed BOOLEAN NOT NULL DEFAULT false,
    started_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at             TIMESTAMPTZ,
    metadata                 JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_botr_status CHECK (status IN (
        'started', 'copied', 'verified', 'failed', 'skipped'
    ))
);

CREATE INDEX IF NOT EXISTS idx_backup_offhost_transfer_run_status
    ON backup_offhost_transfer_runs (backup_run_id, status);

-- ---------------------------------------------------------------------
-- 6. restore_drill_runs -- isolated restore drill results.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS restore_drill_runs (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    backup_run_id               UUID REFERENCES backup_runs(id) ON DELETE CASCADE,
    restore_key                 TEXT NOT NULL UNIQUE,
    target_database             TEXT NOT NULL,
    restore_mode                TEXT NOT NULL,
    status                      TEXT NOT NULL,
    rto_seconds                 NUMERIC,
    row_count_verified          BOOLEAN NOT NULL DEFAULT false,
    schema_verified             BOOLEAN NOT NULL DEFAULT false,
    application_smoke_verified   BOOLEAN NOT NULL DEFAULT false,
    production_restore_performed BOOLEAN NOT NULL DEFAULT false,
    started_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at                TIMESTAMPTZ,
    report_json                 JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata                    JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_rdr_restore_mode CHECK (restore_mode IN (
        'isolated_test_db', 'dry_run', 'metadata_only'
    )),
    CONSTRAINT chk_rdr_status CHECK (status IN (
        'started', 'restored', 'verified', 'failed', 'skipped'
    ))
);

CREATE INDEX IF NOT EXISTS idx_restore_drill_run_status
    ON restore_drill_runs (backup_run_id, status);

-- ---------------------------------------------------------------------
-- 7. backup_schedule_definitions -- schedule spec (NOT a real schedule).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS backup_schedule_definitions (
    id                         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    schedule_key               TEXT NOT NULL UNIQUE,
    schedule_type              TEXT NOT NULL,
    schedule_expression        TEXT NOT NULL,
    command_preview            TEXT NOT NULL,
    enabled                    BOOLEAN NOT NULL DEFAULT false,
    dry_run_validated          BOOLEAN NOT NULL DEFAULT false,
    production_schedule_enabled BOOLEAN NOT NULL DEFAULT false,
    created_at                 TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata                   JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_bsd_schedule_type CHECK (schedule_type IN (
        'cron_spec', 'systemd_timer_spec', 'kubernetes_cronjob_spec', 'dry_run_only'
    ))
);

CREATE INDEX IF NOT EXISTS idx_backup_schedule_def_key
    ON backup_schedule_definitions (schedule_key);

-- ---------------------------------------------------------------------
-- 8. backup_retention_policies -- retention policy.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS backup_retention_policies (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    policy_key     TEXT NOT NULL UNIQUE,
    keep_last      INTEGER NOT NULL DEFAULT 7,
    keep_daily     INTEGER NOT NULL DEFAULT 7,
    keep_weekly    INTEGER NOT NULL DEFAULT 4,
    keep_monthly   INTEGER NOT NULL DEFAULT 3,
    delete_enabled BOOLEAN NOT NULL DEFAULT false,
    dry_run_only   BOOLEAN NOT NULL DEFAULT true,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata       JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- ---------------------------------------------------------------------
-- 9. backup_retention_dry_runs -- retention dry-run results.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS backup_retention_dry_runs (
    id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    policy_id             UUID REFERENCES backup_retention_policies(id) ON DELETE CASCADE,
    status                TEXT NOT NULL,
    candidate_delete_count INTEGER NOT NULL DEFAULT 0,
    actual_delete_count   INTEGER NOT NULL DEFAULT 0,
    dry_run_only          BOOLEAN NOT NULL DEFAULT true,
    report_json           JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_brdr_status CHECK (status IN (
        'completed', 'failed', 'skipped'
    ))
);

-- ---------------------------------------------------------------------
-- 10. migration_rollback_catalog -- migration rollback / down policy.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS migration_rollback_catalog (
    id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    migration_file        TEXT NOT NULL UNIQUE,
    migration_number      INTEGER,
    reversibility         TEXT NOT NULL,
    down_script_available BOOLEAN NOT NULL DEFAULT false,
    rollback_notes        TEXT,
    risk_level            TEXT NOT NULL,
    verified              BOOLEAN NOT NULL DEFAULT false,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata              JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_mrc_reversibility CHECK (reversibility IN (
        'reversible', 'forward_only', 'manual_rollback_required', 'unknown'
    )),
    CONSTRAINT chk_mrc_risk_level CHECK (risk_level IN (
        'low', 'medium', 'high', 'critical'
    ))
);

CREATE INDEX IF NOT EXISTS idx_migration_rollback_catalog_file
    ON migration_rollback_catalog (migration_file);

-- ---------------------------------------------------------------------
-- 11. backup_readiness_evaluations -- backup readiness overall evaluation.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS backup_readiness_evaluations (
    id                       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    evaluation_key           TEXT NOT NULL UNIQUE,
    status                   TEXT NOT NULL,
    encryption_gap_closed    BOOLEAN NOT NULL DEFAULT false,
    offhost_gap_closed       BOOLEAN NOT NULL DEFAULT false,
    schedule_gap_closed      BOOLEAN NOT NULL DEFAULT false,
    migration_down_gap_closed BOOLEAN NOT NULL DEFAULT false,
    remaining_gaps           JSONB NOT NULL DEFAULT '[]'::jsonb,
    limitations              JSONB NOT NULL DEFAULT '[]'::jsonb,
    evaluated_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata                 JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_bre_status CHECK (status IN (
        'passed', 'passed_with_non_production_limitations', 'passed_with_gaps', 'failed'
    ))
);

CREATE INDEX IF NOT EXISTS idx_backup_readiness_eval_key
    ON backup_readiness_evaluations (evaluation_key);

COMMIT;
