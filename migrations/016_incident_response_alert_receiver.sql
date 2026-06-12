-- 016_incident_response_alert_receiver.sql
-- Stage 40 -- Incident Response Runbook & External Alert Receiver.
--
-- Strictly additive and idempotent. Existing incident_records rows are
-- preserved. New tables use IF NOT EXISTS so re-runs are safe.

BEGIN;

-- ---------------------------------------------------------------------------
-- Extend incident_records with Stage 40 columns
-- ---------------------------------------------------------------------------

ALTER TABLE incident_records ADD COLUMN IF NOT EXISTS normalized_severity TEXT;
ALTER TABLE incident_records ADD COLUMN IF NOT EXISTS postmortem_required  BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE incident_records ADD COLUMN IF NOT EXISTS closed_at            TIMESTAMPTZ;

-- Back-fill normalised_severity for pre-existing rows (sev1/sev2 → SEV1_CRITICAL etc.)
UPDATE incident_records
SET    normalized_severity = CASE severity
         WHEN 'sev1' THEN 'SEV1_CRITICAL'
         WHEN 'sev2' THEN 'SEV2_HIGH'
         WHEN 'sev3' THEN 'SEV3_MEDIUM'
         WHEN 'sev4' THEN 'SEV4_LOW'
         ELSE 'SEV5_INFO'
       END
WHERE  normalized_severity IS NULL;

-- ---------------------------------------------------------------------------
-- incident_alerts
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS incident_alerts (
    alert_id             UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    external_alert_id    TEXT,
    source               TEXT        NOT NULL,
    source_type          TEXT        NOT NULL DEFAULT 'generic_webhook',
    alert_name           TEXT        NOT NULL,
    severity             TEXT        NOT NULL,
    normalized_severity  TEXT        NOT NULL,
    status               TEXT        NOT NULL DEFAULT 'received',
    labels               JSONB       NOT NULL DEFAULT '{}'::jsonb,
    annotations          JSONB       NOT NULL DEFAULT '{}'::jsonb,
    raw_payload_hash     TEXT,
    raw_payload_redacted JSONB       NOT NULL DEFAULT '{}'::jsonb,
    received_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    starts_at            TIMESTAMPTZ,
    ends_at              TIMESTAMPTZ,
    fingerprint          TEXT,
    dedupe_key           TEXT        NOT NULL,
    incident_id          UUID,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata             JSONB       NOT NULL DEFAULT '{}'::jsonb
);

-- source_type check: alertmanager | generic_webhook | synthetic_test
ALTER TABLE incident_alerts
    ADD CONSTRAINT IF NOT EXISTS ck_incident_alerts_source_type
    CHECK (source_type IN ('alertmanager','generic_webhook','synthetic_test'));

-- status check
ALTER TABLE incident_alerts
    ADD CONSTRAINT IF NOT EXISTS ck_incident_alerts_status
    CHECK (status IN ('received','deduplicated','linked_to_incident','rejected','suppressed'));

CREATE INDEX IF NOT EXISTS idx_incident_alerts_dedupe_key   ON incident_alerts (dedupe_key);
CREATE INDEX IF NOT EXISTS idx_incident_alerts_fingerprint  ON incident_alerts (fingerprint);
CREATE INDEX IF NOT EXISTS idx_incident_alerts_incident_id  ON incident_alerts (incident_id);
CREATE INDEX IF NOT EXISTS idx_incident_alerts_received_at  ON incident_alerts (received_at);

-- ---------------------------------------------------------------------------
-- incident_lifecycle_events
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS incident_lifecycle_events (
    lifecycle_event_id UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    incident_id        UUID        NOT NULL,
    event_type         TEXT        NOT NULL,
    previous_status    TEXT,
    new_status         TEXT,
    actor_type         TEXT        NOT NULL DEFAULT 'operator',
    actor_id           TEXT,
    reason             TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata           JSONB       NOT NULL DEFAULT '{}'::jsonb
);

ALTER TABLE incident_lifecycle_events
    ADD CONSTRAINT IF NOT EXISTS ck_incident_lifecycle_event_type
    CHECK (event_type IN (
        'incident_created',
        'incident_acknowledged',
        'incident_escalated',
        'incident_resolved',
        'incident_closed',
        'incident_reopened',
        'incident_postmortem_required',
        'incident_postmortem_completed',
        'incident_linked_to_alert',
        'incident_runbook_attached'
    ));

CREATE INDEX IF NOT EXISTS idx_incident_lifecycle_incident_created
    ON incident_lifecycle_events (incident_id, created_at);

-- ---------------------------------------------------------------------------
-- incident_escalation_policies
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS incident_escalation_policies (
    policy_id                UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    policy_name              TEXT        NOT NULL UNIQUE,
    severity                 TEXT        NOT NULL,
    enabled                  BOOLEAN     NOT NULL DEFAULT true,
    dry_run                  BOOLEAN     NOT NULL DEFAULT true,
    escalation_targets       JSONB       NOT NULL DEFAULT '[]'::jsonb,
    escalation_delay_minutes INTEGER     NOT NULL DEFAULT 0,
    repeat_interval_minutes  INTEGER     NOT NULL DEFAULT 60,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata                 JSONB       NOT NULL DEFAULT '{}'::jsonb
);

-- Seed default dry-run escalation policies (idempotent via ON CONFLICT DO NOTHING)
INSERT INTO incident_escalation_policies
    (policy_name, severity, enabled, dry_run, escalation_targets,
     escalation_delay_minutes, repeat_interval_minutes)
VALUES
    ('SEV1_default', 'SEV1_CRITICAL', true,  true,
     '["oncall-primary-placeholder","engineering-lead-placeholder"]'::jsonb, 0,  15),
    ('SEV2_default', 'SEV2_HIGH',     true,  true,
     '["oncall-primary-placeholder"]'::jsonb,                                 5,  30),
    ('SEV3_default', 'SEV3_MEDIUM',   true,  true,
     '["team-channel-placeholder"]'::jsonb,                                  30, 120),
    ('SEV4_default', 'SEV4_LOW',      true,  true,
     '[]'::jsonb,                                                             60, 480),
    ('SEV5_default', 'SEV5_INFO',     true,  true,
     '[]'::jsonb,                                                            120, 1440)
ON CONFLICT (policy_name) DO NOTHING;

-- ---------------------------------------------------------------------------
-- incident_postmortems
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS incident_postmortems (
    postmortem_id      UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    incident_id        UUID        NOT NULL,
    status             TEXT        NOT NULL DEFAULT 'draft',
    summary            TEXT,
    root_cause         TEXT,
    impact             TEXT,
    timeline           JSONB       NOT NULL DEFAULT '[]'::jsonb,
    corrective_actions JSONB       NOT NULL DEFAULT '[]'::jsonb,
    owner              TEXT,
    due_at             TIMESTAMPTZ,
    completed_at       TIMESTAMPTZ,
    document_path      TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata           JSONB       NOT NULL DEFAULT '{}'::jsonb
);

ALTER TABLE incident_postmortems
    ADD CONSTRAINT IF NOT EXISTS ck_incident_postmortems_status
    CHECK (status IN ('draft','in_review','completed','cancelled'));

CREATE INDEX IF NOT EXISTS idx_incident_postmortems_incident_id
    ON incident_postmortems (incident_id);

COMMIT;
