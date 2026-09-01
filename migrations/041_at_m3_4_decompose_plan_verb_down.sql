-- Reverses 041_at_m3_4_decompose_plan_verb.sql: narrows the reasoning verb CHECK back to the
-- three verbs migration 037 admitted.
--
-- It REFUSES rather than deletes when `decompose_plan` invocations already exist. A reasoning
-- invocation is a durable record that a provider was called; narrowing the constraint by removing
-- the rows that no longer fit it would destroy evidence of calls that really happened, which is
-- precisely what AT-M3.1's fail-closed posture exists to prevent. Clear the AT-M3.4 planning data
-- first if that is genuinely intended.

BEGIN;

DO $guard$
DECLARE
    offending BIGINT;
BEGIN
    IF to_regclass('public.reasoning_invocations') IS NULL THEN
        RETURN;
    END IF;

    SELECT count(*) INTO offending
    FROM reasoning_invocations
    WHERE reasoning_verb = 'decompose_plan';

    IF offending > 0 THEN
        RAISE EXCEPTION
            '% reasoning invocation(s) recorded the decompose_plan verb; narrowing the constraint '
            'would leave rows the CHECK forbids. This down migration does not delete reasoning '
            'evidence -- remove the AT-M3.4 planning data deliberately first.', offending;
    END IF;

    ALTER TABLE reasoning_invocations
        DROP CONSTRAINT IF EXISTS chk_reasoning_invocations_verb;

    ALTER TABLE reasoning_invocations
        ADD CONSTRAINT chk_reasoning_invocations_verb CHECK (reasoning_verb IN (
            'propose', 'critique', 'summarize_decision'
        ));
END
$guard$;

COMMIT;
