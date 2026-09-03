-- Step AT-M3.6B.1 -- admit a live reasoning provider and the failure modes only a live one has.
--
-- WHAT THIS DOES. Widens exactly two CHECK constraints on exactly one table
-- (reasoning_invocations, AT-M3.1 / migration 037):
--
--   provider_mode      ('mock','disabled')  ->  ('mock','disabled','live')
--   failure_category   five categories      ->  eight
--
-- Nothing else. No table, no column, no index, no trigger, no function, no backfill, no data
-- change. Migration 040's success/artifact invariant, its lease contract and its terminal-
-- immutability trigger are untouched and keep applying to live rows exactly as they apply to mock
-- ones -- a live invocation is not a privileged invocation.
--
-- WHY `live` AND NOT `anthropic_live`. provider_mode is the provider CLASS, and the question every
-- reader of it asks is "was this real". The vendor is `requested_provider_name` and the model is
-- `model_name`, both of which 037 already provides and 040 already freezes. A vendor-shaped mode
-- would have to be widened again for every vendor, and would force every reader of provider_mode to
-- learn the vendor list before it could answer the one question the column exists for.
--
-- WHY THESE THREE CATEGORIES AND NO MORE. The five AT-M3.1 categories already carry most of what a
-- live path reports: an invalid credential is provider_unauthorized, an outage or a connection reset
-- is provider_unavailable, output that will not parse or will not validate is malformed_output, and
-- a forbidden-key artifact is content_safety_rejected. Three things genuinely could not be said
-- before:
--
--   provider_timeout   the attempt ran out of time. Retryable, and distinguishable from an outage
--                      because the difference decides whether the timeout budget or the provider is
--                      the thing to look at.
--   rate_limited       the provider refused for capacity. Retryable, and NOT an outage: the service
--                      is up and is declining this caller right now.
--   budget_exceeded    the call was refused because it would have cost too much, or because no
--                      authorized budget existed. TERMINAL, and that is the whole point of
--                      separating it -- folding it into provider_unavailable would make an
--                      unaffordable call look retryable and let a runtime re-attempt its way through
--                      a cost ceiling.
--
-- No Anthropic-specific category is added. A vendor's status codes and error bodies are
-- implementation detail; the canonical taxonomy is what a caller reasons about, and it stays small.
--
-- WHAT THIS MIGRATION DOES NOT AUTHORIZE. Nothing. Schema that can REPRESENT a live invocation is
-- not permission to make one: AT-M3.6B.1 authorizes zero live external calls, the runtime gate
-- REASONING_LIVE_NETWORK_ENABLED defaults to false, and opening it is AT-M3.6B.2, which is a
-- separate Product Owner decision that has not been made. This file exists so that the adapter can
-- be built and tested against a real database without the schema being the thing that fails.
--
-- SCOPE. Alters one AT-M3 table. Touches no AT-M2 table -- AT-D14's one schema prohibition.
-- Migrations 001-043 are canonical history and are not modified. Idempotent / re-runnable; a
-- matching *_down.sql reverses it, and fails closed rather than destroying evidence.

BEGIN;

-- --- 1. provider mode --------------------------------------------------------------------------

-- 'mock' and 'disabled' keep their meanings exactly. Nothing is renamed or repurposed.
ALTER TABLE reasoning_invocations
    DROP CONSTRAINT IF EXISTS chk_reasoning_invocations_provider_mode;
ALTER TABLE reasoning_invocations
    ADD CONSTRAINT chk_reasoning_invocations_provider_mode CHECK (provider_mode IN (
        'mock', 'disabled', 'live'
    ));

COMMENT ON COLUMN reasoning_invocations.provider_mode IS
    'The provider CLASS that answered: mock (deterministic, in-process), disabled (refused), or live (a real external model). Not the vendor -- that is requested_provider_name -- and not the model, which is model_name.';

-- --- 2. failure categories ---------------------------------------------------------------------

ALTER TABLE reasoning_invocations
    DROP CONSTRAINT IF EXISTS chk_reasoning_invocations_failure_category;
ALTER TABLE reasoning_invocations
    ADD CONSTRAINT chk_reasoning_invocations_failure_category CHECK (
        failure_category IS NULL OR failure_category IN (
            'provider_disabled',
            'provider_unauthorized',
            'malformed_output',
            'content_safety_rejected',
            'provider_unavailable',
            'provider_timeout',
            'rate_limited',
            'budget_exceeded'
        )
    );

-- --- 3. say out loud what already exists --------------------------------------------------------

DO $live$
DECLARE
    live_rows INT;
BEGIN
    SELECT count(*) INTO live_rows
        FROM reasoning_invocations WHERE provider_mode = 'live';
    IF live_rows > 0 THEN
        RAISE NOTICE
            'AT-M3.6B.1/044: % existing live-mode reasoning invocation(s) are already recorded. This migration widens the vocabulary that admits them; it does not create, modify or authorize any.',
            live_rows;
    END IF;
END;
$live$;

COMMIT;
