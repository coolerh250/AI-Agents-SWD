-- 006_notification_delivery.sql
-- Stage 22 notification delivery surface: one row per notification the
-- notification-worker consumed from stream.notifications + acted on
-- (sandbox simulation, real Discord delivery, or skipped). Strictly
-- additive and idempotent — existing tables are untouched.

BEGIN;

CREATE TABLE IF NOT EXISTS notification_deliveries (
    id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id            TEXT,
    event_type         TEXT NOT NULL DEFAULT 'unknown',
    channel            TEXT NOT NULL DEFAULT 'discord',
    target             TEXT,
    status             TEXT NOT NULL DEFAULT 'simulated',
    sandbox            BOOLEAN NOT NULL DEFAULT TRUE,
    external_sent      BOOLEAN NOT NULL DEFAULT FALSE,
    message_id         TEXT,
    error              TEXT,
    source_message_id  TEXT,
    metadata           JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    delivered_at       TIMESTAMPTZ
);

-- Provide a primary index for the operator UX queries the SDK runs.
CREATE INDEX IF NOT EXISTS idx_notification_deliveries_task_id
    ON notification_deliveries (task_id);
CREATE INDEX IF NOT EXISTS idx_notification_deliveries_status
    ON notification_deliveries (status);
CREATE INDEX IF NOT EXISTS idx_notification_deliveries_created_at
    ON notification_deliveries (created_at DESC);

-- source_message_id is the Redis XADD id of the consumed event. A unique
-- index gives the SDK a cheap idempotent write check without changing the
-- conflict semantics of the existing operator workflow.
--
-- Postgres treats NULLs as distinct in a unique index by default (PG < 15
-- behaviour, also the platform default), so rows whose source_message_id
-- is NULL (e.g. an operator-driven manual delivery) can still coexist
-- without violating the constraint. Older revisions of this migration
-- used a partial WHERE source_message_id IS NOT NULL clause; that worked
-- but did not satisfy the simple ``ON CONFLICT (source_message_id)``
-- predicate the SDK uses. Drop the partial variant if present.
DROP INDEX IF EXISTS uq_notification_deliveries_source_message_id;
CREATE UNIQUE INDEX IF NOT EXISTS uq_notification_deliveries_source_message_id
    ON notification_deliveries (source_message_id);

COMMIT;
