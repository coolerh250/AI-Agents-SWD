-- 015_audit_integrity_key_rotation.sql
-- Stage 39 -- HMAC keyring + audit integrity remediation.
--
-- Adds the metadata table that records which HMAC key IDs the audit
-- integrity SDK has seen and what state each key is in. The key VALUE
-- is never stored; only the opaque key_id + lifecycle metadata.
--
-- Strictly additive + idempotent. Existing tables (audit_logs,
-- audit_integrity_records, audit_chain_verification_runs) are untouched.

BEGIN;

CREATE TABLE IF NOT EXISTS audit_hmac_key_metadata (
    key_id          TEXT PRIMARY KEY,
    key_status      TEXT NOT NULL DEFAULT 'inactive',
    source          TEXT NOT NULL DEFAULT 'unknown',
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    active_from     TIMESTAMPTZ,
    active_until    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_audit_hmac_key_status
        CHECK (key_status IN ('active', 'inactive', 'retired', 'missing', 'invalid')),
    CONSTRAINT chk_audit_hmac_key_source
        CHECK (source IN ('legacy_env', 'keyring_env', 'secret_provider', 'unknown'))
);

CREATE INDEX IF NOT EXISTS idx_audit_hmac_key_metadata_status
    ON audit_hmac_key_metadata (key_status);
CREATE INDEX IF NOT EXISTS idx_audit_hmac_key_metadata_last_seen_at
    ON audit_hmac_key_metadata (last_seen_at);

COMMIT;
