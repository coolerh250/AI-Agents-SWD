-- Step 66C.4-BE1 -- Reminder / Expiry / Controlled Resume data-model foundation.
--
-- ADDITIVE ONLY. This migration:
--   1. Adds exactly six NULLABLE lifecycle columns to operator_clarification_requests
--      (reminder_sent_at, expired_at, resume_eligible_at, resume_requested_at,
--      resume_requested_by, resume_authorized_at) per the canonical
--      docs/contracts/66c4-reminder-expiry-controlled-resume/data-model-contract.md.
--   2. Creates the durable clarification_lifecycle_outbox table (transactional-outbox
--      foundation) per the same canonical contract.
--   3. Adds the partial indexes / CHECK constraint the contract specifies.
--
-- It does NOT create a resume-dispatched timestamp, a resume-authorizer column, an
-- optimistic lock-version column, or any other lifecycle column beyond the six above.
-- Dispatch/resumed evidence lives in the outbox + the task's own status, not in a
-- clarification column (canonical contract, Step 66C.4-P-R1).
--
-- STEP 66C.4-BE1-R1: this file was AMENDED IN PLACE (rather than adding an 032) because 031 has
-- never been merged to main and has never been applied to any shared runtime -- only to isolated
-- ephemeral test databases. Because CREATE TABLE IF NOT EXISTS is a no-op on an existing table,
-- anyone who applied the PRE-R1 version of 031 to a scratch database must run the matching
-- *_down.sql once before re-applying this file, so the outbox table is rebuilt with the three
-- durability columns.
--
-- SAFETY (Step 66C.4-BE1): this migration creates schema only. It wires up NO scheduler,
-- NO outbox relay, and NO runtime producer of lifecycle outbox events. The outbox table
-- is a disabled-by-default foundation with no live consumer and no live writer. Existing
-- answer/audit/event runtime behavior is unchanged by this migration. All new columns are
-- nullable with no default, so every pre-existing row remains valid (no backfill, no
-- destructive rewrite). Idempotent / re-runnable. A matching *_down.sql reverses it.

BEGIN;

-- 1. Additive nullable lifecycle columns on operator_clarification_requests.
ALTER TABLE operator_clarification_requests
    ADD COLUMN IF NOT EXISTS reminder_sent_at     TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS expired_at           TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS resume_eligible_at   TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS resume_requested_at  TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS resume_requested_by  TEXT,
    ADD COLUMN IF NOT EXISTS resume_authorized_at TIMESTAMPTZ;

-- Lifecycle-ordering guard: a resume cannot be authorized before it became eligible.
-- For every pre-existing row all six columns are NULL, so this evaluates to
-- (NULL IS NULL OR ...) = true and never rejects legacy data.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_ocr_resume_authorized_requires_eligible'
    ) THEN
        ALTER TABLE operator_clarification_requests
            ADD CONSTRAINT chk_ocr_resume_authorized_requires_eligible
            CHECK (resume_authorized_at IS NULL OR resume_eligible_at IS NOT NULL);
    END IF;
END$$;

-- Partial indexes supporting the future timeout worker's claim scans (BE2, not built here).
CREATE INDEX IF NOT EXISTS idx_ocr_reminder_due
    ON operator_clarification_requests (status, reminder_at)
    WHERE status = 'open' AND reminder_sent_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_ocr_expiry_due
    ON operator_clarification_requests (status, due_at)
    WHERE status = 'open';

-- 2. Durable transactional-outbox foundation (disabled: no relay, no live producer).
--    Columns are those defined in the canonical data-model-contract.md, INCLUDING the three
--    durability columns added by Step 66C.4-BE1-R1 (available_at / dead_at / last_error).
--    Those three close the blocking sufficiency gap found by the Step 66C.4-BE1-R independent
--    review: without a PERSISTED next-attempt time, binding api-and-event-contract.md 11.3
--    failure mode 1 ("no loss during a publisher outage") and failure mode 7 ("bounded retries
--    end in dead") are mutually unsatisfiable, because a bounded-attempt relay burns its cap
--    within seconds of an outage and dead-letters healthy rows. See
--    be1-r1-outbox-durability-remediation-record.md.
--    Payload is minimal/safe (JSONB) -- never a raw clarification question/answer body,
--    never a secret/token, never a full external channel payload.
CREATE TABLE IF NOT EXISTS clarification_lifecycle_outbox (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    clarification_id  UUID NOT NULL REFERENCES operator_clarification_requests(id),
    task_id           UUID NOT NULL REFERENCES operator_tasks(id),
    event_type        TEXT NOT NULL,
    idempotency_key   TEXT NOT NULL,
    payload           JSONB NOT NULL DEFAULT '{}'::jsonb,
    status            TEXT NOT NULL DEFAULT 'pending',
    attempts          INTEGER NOT NULL DEFAULT 0,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Earliest time a relay may claim this row. Set to statement time on insert, pushed
    -- forward by the backoff policy on each transient failure. NOT NULL so a row can never
    -- become permanently unclaimable through a NULL comparison.
    available_at      TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
    published_at      TIMESTAMPTZ,
    -- Set only when the row reaches the terminal 'dead' state; cleared on operator replay.
    dead_at           TIMESTAMPTZ,
    -- Bounded, secret-free failure reason for the last attempt. Never a payload, never a raw
    -- clarification body, never a credential. Length is bounded here as defense in depth in
    -- addition to the repository-boundary check.
    last_error        TEXT,
    CONSTRAINT uq_clarification_lifecycle_outbox_idempotency_key UNIQUE (idempotency_key),
    CONSTRAINT chk_clo_status CHECK (status IN ('pending', 'published', 'dead')),
    CONSTRAINT chk_clo_attempts_nonnegative CHECK (attempts >= 0),
    CONSTRAINT chk_clo_event_type_nonempty CHECK (length(btrim(event_type)) > 0),
    CONSTRAINT chk_clo_idempotency_key_nonempty CHECK (length(btrim(idempotency_key)) > 0),
    CONSTRAINT chk_clo_last_error_bounded CHECK (last_error IS NULL OR length(last_error) <= 500),
    -- Status/timestamp coherence: pending has neither terminal timestamp; published has
    -- published_at and no dead_at; dead has dead_at and no published_at.
    CONSTRAINT chk_clo_status_timestamps CHECK (
        (status = 'pending'   AND published_at IS NULL     AND dead_at IS NULL)
     OR (status = 'published' AND published_at IS NOT NULL AND dead_at IS NULL)
     OR (status = 'dead'      AND dead_at      IS NOT NULL AND published_at IS NULL)
    )
);

-- Index supporting a future relay's pending-claim scan (oldest first, honoring the persisted
-- backoff schedule). No relay exists in BE1/BE1-R1; this index only prepares for BE2.
CREATE INDEX IF NOT EXISTS idx_clo_pending_available
    ON clarification_lifecycle_outbox (available_at, created_at)
    WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_clo_pending_created
    ON clarification_lifecycle_outbox (created_at)
    WHERE status = 'pending';

-- Index supporting DLQ age / reconciliation reporting over dead rows.
CREATE INDEX IF NOT EXISTS idx_clo_dead_at
    ON clarification_lifecycle_outbox (dead_at)
    WHERE status = 'dead';

CREATE INDEX IF NOT EXISTS idx_clo_clarification_id
    ON clarification_lifecycle_outbox (clarification_id);

COMMIT;
