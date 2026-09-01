-- Reverses 040_at_m3_4_durable_reasoning_artifact.sql.
--
-- This down migration REFUSES rather than destroys, and that refusal is the point of the file.
--
-- Dropping `artifact` would silently delete the only durable copy of structured reasoning outputs
-- that a crashed worker's recovery depends on. Dropping the widened verb CHECK would leave every
-- decompose_plan row in violation of a constraint the database would then have to be lied to
-- about. Dropping `attempt` / `attempt_token` would erase the record of how many times a provider
-- was actually asked -- which is exactly the fact an auditor would come here to check.
--
-- So: if any of that evidence exists, this migration raises and changes nothing. Reversing the
-- schema is only offered while there is nothing to lose by reversing it -- a scratch database that
-- applied 040 and produced no reasoning under the new contract. Deleting the rows first is a
-- deliberate act someone has to perform and account for; it is not something a downgrade does on
-- their behalf.
--
-- Nothing in AT-M3.1's original 037 shape is touched beyond restoring its own verb CHECK.

BEGIN;

DO $guard$
DECLARE
    with_artifact INT;
    plan_rows     INT;
    with_attempts INT;
BEGIN
    SELECT count(*) INTO with_artifact FROM reasoning_invocations WHERE artifact IS NOT NULL;
    SELECT count(*) INTO plan_rows
        FROM reasoning_invocations WHERE reasoning_verb = 'decompose_plan';
    SELECT count(*) INTO with_attempts FROM reasoning_invocations WHERE attempt > 1;

    IF with_artifact > 0 THEN
        RAISE EXCEPTION
            'refusing to downgrade: % reasoning_invocations row(s) carry a durable artifact that dropping this column would destroy. Reasoning evidence is never silently deleted by a migration.',
            with_artifact
            USING ERRCODE = 'restrict_violation';
    END IF;

    IF plan_rows > 0 THEN
        RAISE EXCEPTION
            'refusing to downgrade: % decompose_plan invocation(s) exist and the pre-040 verb CHECK does not admit them. Removing the verb would make the constraint disagree with the rows it guards.',
            plan_rows
            USING ERRCODE = 'restrict_violation';
    END IF;

    IF with_attempts > 0 THEN
        RAISE EXCEPTION
            'refusing to downgrade: % invocation(s) record more than one attempt, and dropping the attempt columns would erase how many times a provider was actually asked.',
            with_attempts
            USING ERRCODE = 'restrict_violation';
    END IF;
END;
$guard$;

DROP TRIGGER IF EXISTS trg_reasoning_invocations_terminal ON reasoning_invocations;
DROP FUNCTION IF EXISTS reasoning_invocations_enforce_terminal();

ALTER TABLE reasoning_invocations
    DROP CONSTRAINT IF EXISTS chk_reasoning_invocations_success_artifact,
    DROP CONSTRAINT IF EXISTS chk_reasoning_invocations_artifact_object,
    DROP CONSTRAINT IF EXISTS chk_reasoning_invocations_artifact_type,
    DROP CONSTRAINT IF EXISTS chk_reasoning_invocations_attempt,
    DROP CONSTRAINT IF EXISTS chk_reasoning_invocations_lease;

ALTER TABLE reasoning_invocations
    DROP COLUMN IF EXISTS artifact_type,
    DROP COLUMN IF EXISTS artifact,
    DROP COLUMN IF EXISTS attempt,
    DROP COLUMN IF EXISTS attempt_token,
    DROP COLUMN IF EXISTS lease_expires_at;

-- Restore 037's own vocabulary exactly.
ALTER TABLE reasoning_invocations
    DROP CONSTRAINT IF EXISTS chk_reasoning_invocations_verb;
ALTER TABLE reasoning_invocations
    ADD CONSTRAINT chk_reasoning_invocations_verb CHECK (reasoning_verb IN (
        'propose', 'critique', 'summarize_decision'
    ));

COMMIT;
