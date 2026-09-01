-- Step AT-M3.4 -- admit the `decompose_plan` reasoning verb.
--
-- ONE constraint, widened. Nothing else in AT-M3.1 changes: no column is added, dropped or
-- retyped, no index moves, no row is touched, and every other CHECK on reasoning_invocations is
-- left exactly as migration 037 wrote it.
--
-- WHY: AT-D14 section 2 defines AT-M3.4 as "the planner producing a draft PlanRevision's work
-- items and dependencies from a Goal and a discussion outcome". Until now no reasoning verb could
-- produce a plan -- `propose`, `critique` and `summarize_decision` all return prose -- so the plan
-- had to arrive from an API caller, and AT-M3.4 Validation 1 demonstrated the consequence: two
-- callers racing the same converged discussion with different plans, and commit ordering deciding
-- which one became "what the team selected". `decompose_plan` is what closes that, and this
-- migration is the database half of it.
--
-- WHY NOT AMEND 037: migration 037 is canonical history, merged and PO-accepted under AT-D15.
-- Rewriting an applied migration would make the file disagree with the databases that ran it.
-- AT-D14 authorizes "the migrations M3.1-M3.5 each need"; its one schema prohibition is on further
-- alteration of an AT-M2 table, and reasoning_invocations is an AT-M3.1 table.
--
-- SAFETY: schema only. Additive and reversible. Starts no container, dispatches nothing, executes
-- nothing, calls no external provider, creates no Approval, and opens no network path -- the new
-- verb is served by the same in-process mock provider every other verb uses. M3.6B remains
-- unauthorized.

BEGIN;

DO $guard$
BEGIN
    IF to_regclass('public.reasoning_invocations') IS NULL THEN
        RAISE EXCEPTION
            'reasoning_invocations does not exist; apply 037_at_m3_reasoning_invocations.sql first';
    END IF;
END
$guard$;

ALTER TABLE reasoning_invocations
    DROP CONSTRAINT IF EXISTS chk_reasoning_invocations_verb;

ALTER TABLE reasoning_invocations
    ADD CONSTRAINT chk_reasoning_invocations_verb CHECK (reasoning_verb IN (
        'propose', 'critique', 'summarize_decision', 'decompose_plan'
    ));

COMMIT;
