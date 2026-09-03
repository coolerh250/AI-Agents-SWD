-- 045_at_m3_6b_1_budget_reservation_down.sql
-- Reverses 045: drops reservation_key, its unique index, its identity constraint, and narrows the
-- event-type vocabulary back to the four Stage 35 shipped.
--
-- IT FAILS CLOSED, and for a sharper reason than 044's does.
--
-- reservation_key is not a label -- it is the only thing that makes an attempt's charge findable,
-- idempotent and settleable. Dropping the column while any row carries one would silently destroy
-- the record of which provider attempt each charge belongs to, and narrowing the vocabulary while
-- an UNSETTLED reservation exists would erase a claim on money that has, as far as anybody knows,
-- already been spent. Either would make the ledger cheaper than the invoice, which is precisely the
-- defect this migration exists to remove.
--
-- So the DOWN refuses while any reservation evidence exists. It does not delete the rows to make
-- itself work: a downgrade is not a licence to discard cost evidence. Settle or reconcile the
-- reservations first, deliberately, and then this will run.

BEGIN;

DO $guard$
DECLARE
    keyed       INT;
    unsettled   INT;
    released    INT;
BEGIN
    SELECT count(*) INTO keyed
        FROM llm_budget_events WHERE reservation_key IS NOT NULL;
    SELECT count(*) INTO unsettled
        FROM llm_budget_events WHERE event_type = 'reserved_usage';
    SELECT count(*) INTO released
        FROM llm_budget_events WHERE event_type = 'released_reservation';

    IF keyed > 0 OR unsettled > 0 OR released > 0 THEN
        RAISE EXCEPTION
            'migration 045 cannot be reversed: % ledger row(s) carry a reservation_key, % reservation(s) are still unsettled and % have been released. Rolling back would destroy the record of which provider attempt each charge belongs to, and would drop unsettled claims on money that may already have been spent. Settle or reconcile them first; this migration will not delete cost evidence to make a downgrade succeed.',
            keyed, unsettled, released
            USING ERRCODE = 'restrict_violation';
    END IF;
END;
$guard$;

ALTER TABLE llm_budget_events
    DROP CONSTRAINT IF EXISTS chk_llm_budget_events_reservation_identity;

ALTER TABLE llm_budget_events
    DROP CONSTRAINT IF EXISTS chk_llm_budget_events_event_type;

ALTER TABLE llm_budget_events
    ADD CONSTRAINT chk_llm_budget_events_event_type
        CHECK (event_type IN (
            'preflight', 'recorded_usage', 'budget_exceeded', 'budget_warning'
        ));

DROP INDEX IF EXISTS uq_llm_budget_events_reservation_key;
DROP INDEX IF EXISTS idx_llm_budget_events_event_type_created_at;

ALTER TABLE llm_budget_events
    DROP COLUMN IF EXISTS reservation_key;

COMMIT;
