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
--    Columns are EXACTLY those defined in the canonical data-model-contract.md; this
--    migration does not self-expand the schema. Basic durable retry state is carried by
--    `attempts` + `status IN ('pending','published','dead')`. Backoff/error-detail columns
--    (e.g. available_at / last_error) are intentionally NOT added here: the canonical
--    contract does not define them, and BE1 must not expand beyond the contract. See
--    be1-disabled-outbox-foundation-record.md, which flags them as a forward
--    contract-refinement item for review before BE2 builds the relay.
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
    published_at      TIMESTAMPTZ,
    CONSTRAINT uq_clarification_lifecycle_outbox_idempotency_key UNIQUE (idempotency_key),
    CONSTRAINT chk_clo_status CHECK (status IN ('pending', 'published', 'dead')),
    CONSTRAINT chk_clo_attempts_nonnegative CHECK (attempts >= 0),
    CONSTRAINT chk_clo_event_type_nonempty CHECK (length(btrim(event_type)) > 0),
    CONSTRAINT chk_clo_idempotency_key_nonempty CHECK (length(btrim(idempotency_key)) > 0)
);

-- Index supporting a future relay's pending-claim scan (oldest first). No relay exists in
-- BE1; this index only prepares for BE2.
CREATE INDEX IF NOT EXISTS idx_clo_pending_created
    ON clarification_lifecycle_outbox (created_at)
    WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_clo_clarification_id
    ON clarification_lifecycle_outbox (clarification_id);

COMMIT;
