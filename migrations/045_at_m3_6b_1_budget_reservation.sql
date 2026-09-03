-- 045_at_m3_6b_1_budget_reservation.sql
-- Step AT-M3.6B.1 remediation -- durable pre-call budget reservation for one provider attempt.
--
-- WHY THIS EXISTS. AT-M3.6B.1 Independent Validation 1 found that a live provider call could land,
-- `record_usage` could then fail, the failure was swallowed, and the day and month totals would
-- understate that charge permanently -- so a later preflight would authorize spend the account
-- could not actually afford. Error handling cannot fix that; only ordering can. A call is now
-- claimed against the budget BEFORE the wire, and a post-call accounting failure can therefore
-- leave the charge conservative but can never leave it at zero.
--
-- WHAT IT ADDS TO llm_budget_events, and nothing else:
--
--   reservation_key    the attempt this row accounts for -- invocation plus attempt number. NEVER
--                      the attempt token: that is ownership-sensitive, it rotates on every retry
--                      and takeover, and a reservation keyed on it could be neither found again nor
--                      made idempotent.
--   a partial UNIQUE index on it, so "one attempt, one charge" is the database's answer rather than
--                      the application's. Eight callers racing for one attempt produce one row.
--   two event types    'reserved_usage' (claimed, call may have occurred) and
--                      'released_reservation' (claimed, and the call PROVABLY never left).
--
-- ONE ROW PER ATTEMPT, FOR ITS WHOLE LIFE. The reservation row is UPDATED into its settlement
-- rather than joined by a second row, which is what lets the usage totals sum reservations and
-- settlements together with no possibility of double counting: while unsettled a row counts at its
-- conservative estimate, once settled at its actual, and there is never a second row to add.
--
-- No new table. No new authority. llm_budget remains the single budget source of truth and nothing
-- reconstructs spend from reasoning_invocations. Migrations 001-044 are untouched, and no existing
-- column, index, constraint or row is modified.

BEGIN;

-- ---------------------------------------------------------------------
-- 1. The attempt identity a reservation is keyed on.
-- ---------------------------------------------------------------------
ALTER TABLE llm_budget_events
    ADD COLUMN IF NOT EXISTS reservation_key TEXT;

COMMENT ON COLUMN llm_budget_events.reservation_key IS
    'The provider attempt this ledger row accounts for (reasoning invocation + attempt number). NULL on every historical row and on every event that is not one attempt''s own accounting. Never an attempt_token.';

-- One attempt, one charge. Partial, because every pre-existing row and every non-attempt event
-- legitimately carries NULL and NULLs must not collide.
CREATE UNIQUE INDEX IF NOT EXISTS uq_llm_budget_events_reservation_key
    ON llm_budget_events (reservation_key)
    WHERE reservation_key IS NOT NULL;

-- ---------------------------------------------------------------------
-- 2. The two event types a reservation lifecycle needs.
-- ---------------------------------------------------------------------
-- 'reserved_usage'        budget claimed before the call. COUNTED against day and month from the
--                         moment it is written, at the conservative estimate that gated the call.
-- 'released_reservation'  the claim given back because the call provably never left. NOT counted.
--                         Written only where absence of an external request can be established --
--                         never on a timeout or a reset connection, where a request may well have
--                         arrived and releasing on that guess would undercount a real charge.
ALTER TABLE llm_budget_events
    DROP CONSTRAINT IF EXISTS chk_llm_budget_events_event_type;

ALTER TABLE llm_budget_events
    ADD CONSTRAINT chk_llm_budget_events_event_type
        CHECK (event_type IN (
            'preflight', 'recorded_usage', 'budget_exceeded', 'budget_warning',
            'reserved_usage', 'released_reservation'
        ));

-- ---------------------------------------------------------------------
-- 3. A reservation is an attempt's accounting, so it must name one.
-- ---------------------------------------------------------------------
-- NOT VALID for the same reason 040's constraints are: it binds every future write without
-- rewriting or invalidating history. There is no history to rewrite here -- neither event type
-- existed before this migration -- but a constraint that would refuse to install against a
-- populated table is a constraint that gets dropped under pressure.
ALTER TABLE llm_budget_events
    DROP CONSTRAINT IF EXISTS chk_llm_budget_events_reservation_identity;

ALTER TABLE llm_budget_events
    ADD CONSTRAINT chk_llm_budget_events_reservation_identity CHECK (
        event_type NOT IN ('reserved_usage', 'released_reservation')
        OR reservation_key IS NOT NULL
    ) NOT VALID;

CREATE INDEX IF NOT EXISTS idx_llm_budget_events_event_type_created_at
    ON llm_budget_events (event_type, created_at DESC);

COMMIT;
