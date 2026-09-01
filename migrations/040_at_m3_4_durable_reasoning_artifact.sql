-- Step AT-M3.4 (rebaselined) -- make a successful reasoning invocation durably replayable.
--
-- WHY THIS EXISTS. AT-M3.1 persisted call METADATA and returned the structured artifact to the
-- caller in memory. That was sufficient while every caller finished its own work in the same
-- process, and AT-M3.3 documented the one case where it is not
-- (agent_deliberation/service.py::_resolve_unowned_turn: "the provider already ran for this turn
-- and its artifact is gone ... Fail closed"). AT-M3.4 made it load-bearing: an invocation could
-- commit status='succeeded' while the artifact existed only as a Python object, so a crash between
-- that commit and the downstream write left the correlation terminal, the artifact unrecoverable,
-- and the work permanently stranded -- no replay could return it and no retry could re-earn it.
--
-- THE INVARIANT THIS MIGRATION MAKES UNREPRESENTABLE:
--
--     status = 'succeeded' with no recoverable artifact.
--
-- The terminal status and the artifact payload are written by the SAME UPDATE to the SAME row, so
-- there is no ordering between them and no window to crash inside. This is why the artifact lives
-- here rather than in a second table: "a succeeded row implies a row over there" is not something
-- a CHECK constraint can say, and every mechanism that can say it (a trigger, a circular NOT NULL
-- foreign key) is a weaker guarantee bought with more moving parts.
--
-- STORAGE PROHIBITION (AT-D03 R8 / INV-04, restated by AT-D14 section 4). Unchanged, and NOT
-- widened by this file. `artifact` holds exactly what _StrictArtifact.as_safe_dict() returns: a
-- closed-schema (extra="forbid") structured business artifact that has already passed the same
-- content-safety screen a TeamMessage passes. No prompt, no completion, no chain-of-thought, no
-- scratchpad, no token trace and no credential becomes storable because this column exists --
-- those are rejected at the model layer before a value ever reaches here. This introduces no new
-- CLASS of persisted data either: AT-M3.3 already writes these identical payloads into
-- team_messages.content on every discussion turn. What is new is the ROLE -- this copy is a
-- recovery copy, read only to rebuild what a crashed worker was holding, and it is never a second
-- product authority over the copy the team can actually see.
--
-- LEASE / TAKEOVER. 037 deferred recovery of a stranded 'started' row explicitly ("no lease/
-- takeover mechanism is added by this slice"), which left a second, independent way to strand
-- work: a worker that dies before its terminal UPDATE owns that correlation_id forever, and every
-- later caller is told 'in_progress' in perpetuity. AT-M3.3 escapes this through its own
-- discussion deadline; AT-M3.4 has no deadline and would not. Ownership is therefore now bounded
-- by lease_expires_at on the DATABASE clock -- never an application wall clock, which a paused or
-- skewed worker could use to extend its own ownership -- and an expired lease is takeable by
-- exactly one contender through a compare-and-swap, bounded by attempt.
--
-- LEGACY ROWS (the honest part). canonical main may already hold succeeded rows carrying no
-- artifact, written under the AT-M3.1 contract. They are truthful evidence of calls that really
-- happened, so this migration does not fabricate artifacts for them, does not rewrite them as
-- failed, and does not delete them. The artifact-presence and lease CHECKs are therefore added
-- NOT VALID: PostgreSQL enforces a NOT VALID CHECK on every INSERT and every UPDATE from this
-- point on, and skips only the retroactive scan. Old rows stay exactly as they are and are
-- readable as what they are -- legacy metadata-only evidence -- while no NEW write can reach the
-- state this migration exists to forbid. This is a compatibility choice, not an exemption
-- mechanism: nothing here can be invoked to excuse a future row.
--
-- A decompose_plan invocation can never be legacy, because the verb did not exist on canonical
-- main. Every row AT-M3.4 will ever read is subject to the full invariant.
--
-- SCOPE. Alters exactly one table, reasoning_invocations (AT-M3.1). Creates no table, drops
-- nothing, backfills nothing and touches no AT-M2 table -- AT-D14's one schema prohibition. 037
-- is canonical history and is not rewritten; a widened constraint is a new file. Idempotent /
-- re-runnable; a matching *_down.sql reverses it.

BEGIN;

-- --- 1. the durable artifact, and the attempt that produced it -------------------------------

ALTER TABLE reasoning_invocations
    -- The artifact CLASS, so a reader knows which model to rebuild the payload through without
    -- re-deriving it from the verb. Constrained below to agree with the verb, so the two can
    -- never drift into disagreeing about what this row holds.
    ADD COLUMN IF NOT EXISTS artifact_type    TEXT,
    -- _StrictArtifact.as_safe_dict(). NULL unless this row is terminally succeeded.
    ADD COLUMN IF NOT EXISTS artifact         JSONB,
    -- 1 for the original claim; incremented once per takeover of an expired lease.
    ADD COLUMN IF NOT EXISTS attempt          INT NOT NULL DEFAULT 1,
    -- Identifies the CURRENT attempt's owner. complete_invocation is guarded on it, so a zombie
    -- worker that wakes up after its lease was taken over learns it lost instead of silently
    -- terminalizing a result nobody is waiting for.
    ADD COLUMN IF NOT EXISTS attempt_token    UUID,
    -- DB-clock ownership bound. NULL on a terminal row (nobody owns a finished call) and NULL on
    -- a legacy 'started' row claimed before this contract existed -- which is precisely what makes
    -- those legacy rows recoverable rather than permanently stranded.
    ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ;

COMMENT ON COLUMN reasoning_invocations.artifact IS
    'Recovery copy of the validated safe structured artifact. Never a prompt, completion, hidden reasoning or credential. Not a second product authority over TeamMessage.content.';
COMMENT ON COLUMN reasoning_invocations.lease_expires_at IS
    'Database-clock ownership lease. NULL when terminal, or when the row predates this contract.';

-- --- 2. the verb vocabulary ------------------------------------------------------------------

-- AT-M3.4 adds one verb. The three that existed keep their meanings exactly; nothing is renamed
-- or repurposed.
ALTER TABLE reasoning_invocations
    DROP CONSTRAINT IF EXISTS chk_reasoning_invocations_verb;
ALTER TABLE reasoning_invocations
    ADD CONSTRAINT chk_reasoning_invocations_verb CHECK (reasoning_verb IN (
        'propose', 'critique', 'summarize_decision', 'decompose_plan'
    ));

-- --- 3. success carries its artifact ----------------------------------------------------------

-- The load-bearing one. NOT VALID for the legacy reason above; still fully enforced on every new
-- INSERT and every UPDATE, which is what makes the invariant real going forward.
ALTER TABLE reasoning_invocations
    DROP CONSTRAINT IF EXISTS chk_reasoning_invocations_success_artifact;
ALTER TABLE reasoning_invocations
    ADD CONSTRAINT chk_reasoning_invocations_success_artifact CHECK (
        (status = 'succeeded' AND artifact_type IS NOT NULL AND artifact IS NOT NULL)
        OR (status <> 'succeeded' AND artifact_type IS NULL AND artifact IS NULL)
    ) NOT VALID;

-- A JSON scalar or array is not an artifact. Valid outright: no legacy row has an artifact at all.
ALTER TABLE reasoning_invocations
    DROP CONSTRAINT IF EXISTS chk_reasoning_invocations_artifact_object;
ALTER TABLE reasoning_invocations
    ADD CONSTRAINT chk_reasoning_invocations_artifact_object CHECK (
        artifact IS NULL OR jsonb_typeof(artifact) = 'object'
    );

-- artifact_type is not free text: it is the verb's own artifact class, spelled out per verb so
-- that adding a verb requires editing this list rather than silently admitting a new class name.
-- Mirrors ARTIFACT_TYPE_FOR_VERB in shared/sdk/agent_reasoning/models.py.
ALTER TABLE reasoning_invocations
    DROP CONSTRAINT IF EXISTS chk_reasoning_invocations_artifact_type;
ALTER TABLE reasoning_invocations
    ADD CONSTRAINT chk_reasoning_invocations_artifact_type CHECK (
        artifact_type IS NULL OR (
            (reasoning_verb = 'propose' AND artifact_type = 'ProposalArtifact')
            OR (reasoning_verb = 'critique' AND artifact_type = 'CritiqueArtifact')
            OR (reasoning_verb = 'summarize_decision' AND artifact_type = 'DecisionSummaryArtifact')
            OR (reasoning_verb = 'decompose_plan' AND artifact_type = 'PlanDraftArtifact')
        )
    );

-- --- 4. ownership -----------------------------------------------------------------------------

ALTER TABLE reasoning_invocations
    DROP CONSTRAINT IF EXISTS chk_reasoning_invocations_attempt;
ALTER TABLE reasoning_invocations
    ADD CONSTRAINT chk_reasoning_invocations_attempt CHECK (attempt >= 1);

-- A live call is owned and time-bounded; a finished call is owned by nobody. NOT VALID because a
-- legacy 'started' row carries neither token nor lease -- and reading that as "unowned", rather
-- than rewriting it, is what lets a legacy stranded attempt finally make progress.
ALTER TABLE reasoning_invocations
    DROP CONSTRAINT IF EXISTS chk_reasoning_invocations_lease;
ALTER TABLE reasoning_invocations
    ADD CONSTRAINT chk_reasoning_invocations_lease CHECK (
        (status = 'started' AND attempt_token IS NOT NULL AND lease_expires_at IS NOT NULL)
        OR (status <> 'started' AND lease_expires_at IS NULL)
    ) NOT VALID;

-- --- 5. a terminal invocation is frozen -------------------------------------------------------

-- Service discipline is not enough: the whole point of a recovery copy is that some other process
-- can be trusted to read it, and "trusted" has to survive a raw SQL caller. Once a row is
-- terminal, its outcome, its artifact, its provider identity and its attempt ownership cannot be
-- edited at all -- a successful artifact can never be replaced with a different valid one.
--
-- project_id, thread_id and requested_by_principal_id are deliberately NOT frozen: they are
-- ON DELETE SET NULL lifecycle references, and freezing them would make deleting a project fail
-- against reasoning history rather than detach from it.
CREATE OR REPLACE FUNCTION reasoning_invocations_enforce_terminal() RETURNS TRIGGER AS $fn$
BEGIN
    -- (a) Identity and provider identity: immutable in every status, including 'started'. A
    --     takeover re-owns an attempt; it never re-labels what the call IS.
    IF NEW.invocation_id           IS DISTINCT FROM OLD.invocation_id
    OR NEW.correlation_id          IS DISTINCT FROM OLD.correlation_id
    OR NEW.reasoning_verb          IS DISTINCT FROM OLD.reasoning_verb
    OR NEW.requested_provider_name IS DISTINCT FROM OLD.requested_provider_name
    OR NEW.provider_mode           IS DISTINCT FROM OLD.provider_mode
    OR NEW.model_name              IS DISTINCT FROM OLD.model_name
    OR NEW.created_at              IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION
            'reasoning_invocations: the identity and provider identity of invocation % are immutable',
            OLD.invocation_id
            USING ERRCODE = 'restrict_violation';
    END IF;

    -- (b) Attempts count up. Rewinding one would make the audit trail lie about how many times a
    --     provider was actually asked.
    IF NEW.attempt < OLD.attempt THEN
        RAISE EXCEPTION
            'reasoning_invocations: attempt may not decrease (% -> %) for invocation %',
            OLD.attempt, NEW.attempt, OLD.invocation_id
            USING ERRCODE = 'restrict_violation';
    END IF;

    -- (c) Terminal rows are frozen.
    IF OLD.status <> 'started' THEN
        IF NEW.status           IS DISTINCT FROM OLD.status
        OR NEW.artifact_type    IS DISTINCT FROM OLD.artifact_type
        OR NEW.artifact         IS DISTINCT FROM OLD.artifact
        OR NEW.failure_category IS DISTINCT FROM OLD.failure_category
        OR NEW.failure_reason   IS DISTINCT FROM OLD.failure_reason
        OR NEW.attempt          IS DISTINCT FROM OLD.attempt
        OR NEW.attempt_token    IS DISTINCT FROM OLD.attempt_token
        OR NEW.lease_expires_at IS DISTINCT FROM OLD.lease_expires_at
        OR NEW.started_at       IS DISTINCT FROM OLD.started_at
        OR NEW.completed_at     IS DISTINCT FROM OLD.completed_at
        OR NEW.latency_ms       IS DISTINCT FROM OLD.latency_ms
        OR NEW.round_number     IS DISTINCT FROM OLD.round_number
        OR NEW.audit_ref        IS DISTINCT FROM OLD.audit_ref THEN
            RAISE EXCEPTION
                'reasoning_invocations is terminal-immutable: invocation % already recorded % and its outcome, artifact, provider identity and attempt ownership may not be edited',
                OLD.invocation_id, OLD.status
                USING ERRCODE = 'restrict_violation';
        END IF;

        -- outcome_ref remains what 037 declared it to be: an informational forward reference a
        -- later slice may set once. It is NOT load-bearing -- recovery reads `artifact`, which is
        -- a typed column with a constraint, not a string with a convention.
        IF NEW.outcome_ref IS DISTINCT FROM OLD.outcome_ref AND OLD.outcome_ref IS NOT NULL THEN
            RAISE EXCEPTION
                'reasoning_invocations.outcome_ref is write-once: invocation % already carries one',
                OLD.invocation_id
                USING ERRCODE = 'restrict_violation';
        END IF;
    END IF;

    RETURN NEW;
END;
$fn$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_reasoning_invocations_terminal ON reasoning_invocations;
CREATE TRIGGER trg_reasoning_invocations_terminal
    BEFORE UPDATE ON reasoning_invocations
    FOR EACH ROW EXECUTE FUNCTION reasoning_invocations_enforce_terminal();

-- --- 6. say out loud what was inherited -------------------------------------------------------

DO $legacy$
DECLARE
    stale_success INT;
    stale_started INT;
BEGIN
    SELECT count(*) INTO stale_success
        FROM reasoning_invocations WHERE status = 'succeeded' AND artifact IS NULL;
    SELECT count(*) INTO stale_started
        FROM reasoning_invocations WHERE status = 'started' AND lease_expires_at IS NULL;
    IF stale_success > 0 OR stale_started > 0 THEN
        RAISE NOTICE
            'AT-M3.4/040: % legacy metadata-only succeeded row(s) and % unleased started row(s) predate the durable-artifact contract. They are preserved unchanged and remain legacy evidence; every new write is fully constrained.',
            stale_success, stale_started;
    END IF;
END;
$legacy$;

COMMIT;
