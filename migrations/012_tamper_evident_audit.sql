-- 012_tamper_evident_audit.sql
-- Stage 34 -- tamper-evident audit chain.
--
-- Two new tables sit BESIDE the existing ``audit_logs`` table (which is
-- not modified):
--
--   (1) audit_integrity_records       -- per-audit-row hash-chain entry
--                                       (sequence_number, prev_hash,
--                                       row_hash, canonical_payload_hash,
--                                       optional HMAC signature).
--   (2) audit_chain_verification_runs -- one row per verify-chain pass,
--                                       with status / counters / failure
--                                       coordinates.
--
-- Strictly additive + idempotent. Existing tables (audit_logs,
-- notification_deliveries, deployment_records, workflow_states,
-- task_work_items, llm_*, code_*, qa_*, human_approval_*, ...) are
-- untouched. The audit_logs primary key is ``id`` UUID (verified via
-- the on-cluster ``\d+ audit_logs`` inspection before this migration was
-- written) so ``audit_log_id`` here is also UUID.

BEGIN;

-- ---------------------------------------------------------------------
-- 1. audit_integrity_records -- one row per audit_logs row, ordered by
--    sequence_number, with prev_hash -> row_hash forming the chain.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_integrity_records (
    integrity_id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    audit_log_id            UUID NOT NULL,
    chain_version           INTEGER NOT NULL DEFAULT 1,
    sequence_number         BIGINT NOT NULL,
    prev_hash               TEXT,
    row_hash                TEXT NOT NULL,
    canonical_payload_hash  TEXT NOT NULL,
    hmac_signature          TEXT,
    signing_key_id          TEXT,
    signature_status        TEXT NOT NULL DEFAULT 'unsigned',
    integrity_status        TEXT NOT NULL DEFAULT 'active',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_audit_integrity_audit_log_id UNIQUE (audit_log_id),
    CONSTRAINT uq_audit_integrity_sequence
        UNIQUE (chain_version, sequence_number),
    CONSTRAINT chk_audit_integrity_signature_status
        CHECK (signature_status IN ('unsigned', 'signed', 'signing_key_not_configured')),
    CONSTRAINT chk_audit_integrity_status
        CHECK (integrity_status IN ('active', 'backfilled', 'invalidated'))
);

CREATE INDEX IF NOT EXISTS idx_audit_integrity_row_hash
    ON audit_integrity_records (row_hash);
CREATE INDEX IF NOT EXISTS idx_audit_integrity_created_at
    ON audit_integrity_records (created_at);
CREATE INDEX IF NOT EXISTS idx_audit_integrity_chain_version
    ON audit_integrity_records (chain_version);
CREATE INDEX IF NOT EXISTS idx_audit_integrity_audit_log_id
    ON audit_integrity_records (audit_log_id);

-- ---------------------------------------------------------------------
-- 2. audit_chain_verification_runs -- one row per verify-chain pass.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_chain_verification_runs (
    verification_id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chain_version                INTEGER NOT NULL DEFAULT 1,
    status                       TEXT NOT NULL,
    total_records                INTEGER NOT NULL DEFAULT 0,
    verified_records             INTEGER NOT NULL DEFAULT 0,
    failed_records               INTEGER NOT NULL DEFAULT 0,
    first_failure_sequence       BIGINT,
    first_failure_audit_log_id   UUID,
    failure_reason               TEXT,
    started_at                   TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at                 TIMESTAMPTZ,
    metadata                     JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_audit_chain_verification_status
        CHECK (status IN ('passed', 'failed', 'partial', 'error'))
);

CREATE INDEX IF NOT EXISTS idx_audit_chain_verification_runs_status
    ON audit_chain_verification_runs (status);
CREATE INDEX IF NOT EXISTS idx_audit_chain_verification_runs_started_at
    ON audit_chain_verification_runs (started_at);
CREATE INDEX IF NOT EXISTS idx_audit_chain_verification_runs_chain_version
    ON audit_chain_verification_runs (chain_version);

COMMIT;
