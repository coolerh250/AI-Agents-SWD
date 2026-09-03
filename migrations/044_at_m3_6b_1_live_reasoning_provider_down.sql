-- Step AT-M3.6B.1 -- reverse migration 044.
--
-- Narrows provider_mode back to ('mock','disabled') and failure_category back to AT-M3.1's five.
--
-- FAILS CLOSED. If any row already records a live-mode invocation, or a failure in one of the three
-- categories 044 added, this migration raises and rolls back rather than proceeding. That is
-- deliberate and it is the only honest option: the alternative ways to make a DOWN "succeed" here
-- are to delete those rows or to rewrite them as something they were not, and both destroy the
-- record of provider calls that really happened. A reasoning invocation is evidence -- migration 040
-- exists precisely to stop that evidence being edited -- and a schema rollback is not a licence to
-- edit it.
--
-- To roll back after live rows exist, an operator must first decide what should become of that
-- history and record that decision. This file will not decide it for them.

BEGIN;

DO $guard$
DECLARE
    live_rows      INT;
    new_category_rows INT;
BEGIN
    SELECT count(*) INTO live_rows
        FROM reasoning_invocations WHERE provider_mode = 'live';
    SELECT count(*) INTO new_category_rows
        FROM reasoning_invocations
        WHERE failure_category IN ('provider_timeout', 'rate_limited', 'budget_exceeded');

    IF live_rows > 0 OR new_category_rows > 0 THEN
        RAISE EXCEPTION
            'AT-M3.6B.1/044 DOWN refused: % live-mode invocation(s) and % invocation(s) in a failure category this rollback removes already exist. Reverting would make real reasoning history unrepresentable, and this migration will not delete or relabel it to succeed.',
            live_rows, new_category_rows
            USING ERRCODE = 'restrict_violation';
    END IF;
END;
$guard$;

ALTER TABLE reasoning_invocations
    DROP CONSTRAINT IF EXISTS chk_reasoning_invocations_provider_mode;
ALTER TABLE reasoning_invocations
    ADD CONSTRAINT chk_reasoning_invocations_provider_mode CHECK (provider_mode IN (
        'mock', 'disabled'
    ));

COMMENT ON COLUMN reasoning_invocations.provider_mode IS NULL;

ALTER TABLE reasoning_invocations
    DROP CONSTRAINT IF EXISTS chk_reasoning_invocations_failure_category;
ALTER TABLE reasoning_invocations
    ADD CONSTRAINT chk_reasoning_invocations_failure_category CHECK (
        failure_category IS NULL OR failure_category IN (
            'provider_disabled',
            'provider_unauthorized',
            'malformed_output',
            'content_safety_rejected',
            'provider_unavailable'
        )
    );

COMMIT;
