-- Step AT-M3.3 -- bounded, capability-aware team discussion.
--
-- Implements the slice AT-D14 section 2 authorizes as "propose/challenge/converge over the
-- EXISTING ConversationThread/TeamMessage schema; max-rounds/timeout/budget bounds; fail-closed
-- terminal states", against docs/architecture/autonomous-team/collaboration-and-workroom-model.md.
--
-- ADDITIVE ONLY. Three new tables. It adds no column to, and changes no constraint on, any
-- existing table -- deliberately, because AT-D14 pre-cleared exactly ONE alteration of an AT-M2
-- table (the team_decisions FK AT-M3.2 already made) and "authorizes no other alteration of an
-- AT-M2 table". In particular chk_team_messages_type is NOT widened: the discussion's own intent
-- vocabulary lives in discussion_turns.intent below, and each turn's message is posted under a
-- message_type the AT-M2 contract already defines.
--
-- WHAT IS REUSED, NOT REBUILT:
--   conversation_threads  the discussion IS a thread (one row, 1:1). No second conversation
--                         hierarchy is introduced -- discussion_sessions carries the bounded
--                         ORCHESTRATION state a thread has no place to hold, and nothing else.
--   team_messages         every word a participant says is a TeamMessage. No second message
--                         table exists here; discussion_turns holds no body, only the ledger
--                         entry that says which turn produced which message.
--   actor_principals /    participants are selected from the project's existing team by the
--   agent_profiles /      existing AT-M2 capability router. No second agent registry.
--   project_team_memberships
--   goals / plan_revisions the discussion's subject matter, by foreign key.
--   reasoning_invocations every reasoning turn correlates to one AT-M3.1 invocation row.
--
-- TERMINAL STATE AND STOP REASON ARE SEPARATE CONCEPTS, and the CHECK below keeps them honest:
-- 'converged' is reachable ONLY with stop_reason 'convergence_reached', and the three budget
-- exhaustion reasons are reachable ONLY as 'exhausted'. A discussion that merely ran out of
-- rounds can therefore never be recorded as consensus, which is the specific failure this
-- constraint exists to make unrepresentable.
--
-- CONCURRENCY: uq_discussion_turns_slot is the execution-ownership authority. Advancing a
-- discussion claims (discussion_id, round_index, seat_index) with INSERT ... ON CONFLICT DO
-- NOTHING BEFORE any provider call, exactly as AT-M3.1's correlation_id claim does for a
-- reasoning invocation -- so of N workers racing the same next turn, exactly one proceeds and the
-- others learn they lost from the database rather than from a prior SELECT. The turn's
-- correlation_id is derived deterministically from that same slot, so AT-M3.1's own UNIQUE
-- constraint independently prevents a second provider call for one turn. Two layers, both in
-- PostgreSQL, neither depending on process memory.
--
-- RESUMABILITY: current_round, the turn ledger and every budget counter are columns, not
-- in-memory state. A new process reconstructs the next turn from these rows alone.
--
-- STORAGE PROHIBITION (AT-D03 R8 / INV-04, restated by AT-D14 section 4): no column below holds a
-- prompt, a completion, hidden reasoning, a scratchpad, a token trace or a credential. The
-- assembled reasoning context is never persisted by anything in this slice. Discussion bodies
-- live in team_messages, which AT-M2 already screens.
--
-- SAFETY: schema only. Starts no container, dispatches nothing, executes nothing, calls no
-- external provider. Idempotent / re-runnable; a matching *_down.sql reverses it.

BEGIN;

-- ---------------------------------------------------------------------
-- 1. discussion_sessions -- one bounded deliberation.
--
--    Bound to the project, the Goal, the PlanRevision the team is deliberating against, the
--    thread that carries the conversation, and the actor that opened it. Everything a resumed
--    process needs is here or in the two ledgers below.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS discussion_sessions (
    discussion_id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id                UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    goal_id                   UUID NOT NULL REFERENCES goals(goal_id) ON DELETE CASCADE,
    -- The revision under discussion. NULL when the Goal has no plan yet -- which is a legitimate
    -- starting point, since deciding what the first plan should be is itself a discussion.
    plan_revision_id          UUID REFERENCES plan_revisions(plan_revision_id) ON DELETE SET NULL,
    -- One thread per discussion, and one discussion per thread. The thread is the conversation;
    -- this row is only its bounds and its cursor.
    thread_id                 UUID NOT NULL UNIQUE REFERENCES conversation_threads(thread_id)
                                   ON DELETE CASCADE,
    opened_by                 UUID NOT NULL REFERENCES actor_principals(principal_id),
    -- The explicit question the team is deliberating. A discussion without one cannot converge,
    -- because nothing says what it would have converged ON.
    topic                     TEXT NOT NULL,
    -- The capabilities the topic needs. Participants are selected against exactly these.
    required_capabilities     JSONB NOT NULL DEFAULT '[]'::jsonb,

    -- Bounds. Persisted, never inferred, so a resumed process enforces the same limits the
    -- opening process was given.
    max_rounds                INT NOT NULL,
    max_messages              INT NOT NULL,
    max_invocations           INT NOT NULL,
    max_turns_per_participant INT NOT NULL,

    -- Cursor and budget consumption.
    current_round             INT NOT NULL DEFAULT 1,
    turns_taken               INT NOT NULL DEFAULT 0,
    messages_posted           INT NOT NULL DEFAULT 0,
    invocations_started       INT NOT NULL DEFAULT 0,

    state                     TEXT NOT NULL DEFAULT 'open',
    -- NULL exactly while the discussion is open; required the moment it is not.
    stop_reason               TEXT,
    -- The durable discussion result M3.4 consumes: the convergence-summary TeamMessage. It is a
    -- MESSAGE, never a TeamDecision -- recording what the team said is not the team deciding.
    result_message_id         UUID REFERENCES team_messages(message_id) ON DELETE SET NULL,
    -- Duplicate-start protection. Derived from (project, goal, plan revision, topic) when the
    -- caller supplies nothing, so an accidental double start resolves to the same discussion.
    idempotency_key           TEXT NOT NULL UNIQUE,
    audit_ref                 TEXT,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at                 TIMESTAMPTZ,

    CONSTRAINT chk_discussion_sessions_topic CHECK (
        length(btrim(topic)) > 0 AND length(topic) <= 2000
    ),
    CONSTRAINT chk_discussion_sessions_capabilities CHECK (
        jsonb_typeof(required_capabilities) = 'array'
    ),
    CONSTRAINT chk_discussion_sessions_state CHECK (state IN (
        'open', 'converged', 'exhausted', 'failed', 'cancelled'
    )),
    CONSTRAINT chk_discussion_sessions_stop_reason CHECK (stop_reason IS NULL OR stop_reason IN (
        'convergence_reached',
        'round_limit_reached',
        'message_limit_reached',
        'invocation_limit_reached',
        'participant_unavailable',
        'reasoning_provider_failure',
        'cancelled',
        'insufficient_capability_coverage'
    )),
    -- Open iff no stop reason. A terminal row always says why it stopped.
    CONSTRAINT chk_discussion_sessions_terminal CHECK (
        (state = 'open') = (stop_reason IS NULL)
    ),
    -- The reason must belong to the state. This is what makes "the team agreed" and "the team
    -- ran out of rounds" impossible to confuse.
    CONSTRAINT chk_discussion_sessions_reason_matches_state CHECK (
        stop_reason IS NULL
        OR (state = 'converged' AND stop_reason = 'convergence_reached')
        OR (state = 'exhausted' AND stop_reason IN (
                'round_limit_reached', 'message_limit_reached', 'invocation_limit_reached'))
        OR (state = 'failed' AND stop_reason IN (
                'participant_unavailable', 'reasoning_provider_failure',
                'insufficient_capability_coverage'))
        OR (state = 'cancelled' AND stop_reason = 'cancelled')
    ),
    -- Only a converged discussion carries a result for M3.4 to consume.
    CONSTRAINT chk_discussion_sessions_result CHECK (
        result_message_id IS NULL OR state = 'converged'
    ),
    CONSTRAINT chk_discussion_sessions_bounds CHECK (
        max_rounds BETWEEN 1 AND 20
        AND max_messages BETWEEN 1 AND 200
        AND max_invocations BETWEEN 1 AND 200
        AND max_turns_per_participant BETWEEN 1 AND 20
    ),
    CONSTRAINT chk_discussion_sessions_counters CHECK (
        current_round >= 1 AND turns_taken >= 0 AND messages_posted >= 0
        AND invocations_started >= 0
    )
);

CREATE INDEX IF NOT EXISTS idx_discussion_sessions_project
    ON discussion_sessions (project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_discussion_sessions_goal
    ON discussion_sessions (goal_id, created_at);
CREATE INDEX IF NOT EXISTS idx_discussion_sessions_open
    ON discussion_sessions (project_id) WHERE state = 'open';

-- ---------------------------------------------------------------------
-- 2. discussion_participants -- who was invited, and the evidence for why.
--
--    NOT a second agent registry: principal_id is an existing actor_principals row that the
--    existing capability router selected from the project's existing team. This table records
--    the selection and fixes a deterministic speaking order.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS discussion_participants (
    participant_id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    discussion_id         UUID NOT NULL REFERENCES discussion_sessions(discussion_id)
                               ON DELETE CASCADE,
    principal_id          UUID NOT NULL REFERENCES actor_principals(principal_id),
    agent_key             TEXT NOT NULL,
    functional_role       TEXT NOT NULL,
    -- Which of the discussion's required capabilities this participant was selected for.
    matched_capabilities  JSONB NOT NULL DEFAULT '[]'::jsonb,
    -- The router's own reason, carried through verbatim rather than re-derived.
    selection_reason      TEXT NOT NULL,
    -- Speaking order. Seat 0 opens the discussion with the proposal.
    seat_index            INT NOT NULL,
    turns_taken           INT NOT NULL DEFAULT 0,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT chk_discussion_participants_seat CHECK (seat_index >= 0),
    CONSTRAINT chk_discussion_participants_capabilities CHECK (
        jsonb_typeof(matched_capabilities) = 'array'
    ),
    CONSTRAINT chk_discussion_participants_reason CHECK (length(btrim(selection_reason)) > 0),
    -- One seat per principal, one principal per seat. A duplicate invitation is unrepresentable
    -- rather than de-duplicated after the fact.
    CONSTRAINT uq_discussion_participants_principal UNIQUE (discussion_id, principal_id),
    CONSTRAINT uq_discussion_participants_seat UNIQUE (discussion_id, seat_index)
);

CREATE INDEX IF NOT EXISTS idx_discussion_participants_discussion
    ON discussion_participants (discussion_id, seat_index);

-- ---------------------------------------------------------------------
-- 3. discussion_turns -- the turn ledger, and the concurrency authority.
--
--    Holds NO message body. It records that slot (round, seat) was claimed, by whom, with which
--    reasoning invocation, producing which TeamMessage.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS discussion_turns (
    turn_id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    discussion_id           UUID NOT NULL REFERENCES discussion_sessions(discussion_id)
                                 ON DELETE CASCADE,
    round_index             INT NOT NULL,
    -- 0..n-1 are the participants' seats. n is the session's own convergence-summary turn, which
    -- is spoken by seat 0 and belongs to no participant's budget.
    seat_index              INT NOT NULL,
    speaker_principal_id    UUID NOT NULL REFERENCES actor_principals(principal_id),
    addressed_principal_id  UUID REFERENCES actor_principals(principal_id),
    addressed_team          BOOLEAN NOT NULL DEFAULT false,
    -- The DISCUSSION-level intent. Derived from the reasoning artifact, not assigned by a fixed
    -- script: a critique carrying concerns is a challenge, one carrying none is support. This is
    -- what the convergence signal reads. It is deliberately separate from the TeamMessage's
    -- message_type, which stays inside the AT-M2 vocabulary.
    intent                  TEXT NOT NULL,
    reasoning_verb          TEXT NOT NULL,
    reasoning_invocation_id UUID REFERENCES reasoning_invocations(invocation_id)
                                 ON DELETE SET NULL,
    message_id              UUID REFERENCES team_messages(message_id) ON DELETE SET NULL,
    -- Derived deterministically from (discussion_id, round_index, seat_index), so a retried turn
    -- is recognised by AT-M3.1 as the same logical attempt rather than a new one.
    correlation_id          UUID NOT NULL,
    status                  TEXT NOT NULL DEFAULT 'claimed',
    -- Number of unresolved concerns the turn's artifact carried. The convergence signal is a
    -- function of these, not of how many rounds have elapsed.
    concern_count           INT NOT NULL DEFAULT 0,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at            TIMESTAMPTZ,

    CONSTRAINT chk_discussion_turns_round CHECK (round_index >= 1),
    CONSTRAINT chk_discussion_turns_seat CHECK (seat_index >= 0),
    CONSTRAINT chk_discussion_turns_concerns CHECK (concern_count >= 0),
    CONSTRAINT chk_discussion_turns_intent CHECK (intent IN (
        'proposal', 'challenge', 'response', 'observation', 'clarification',
        'support', 'objection', 'convergence_summary'
    )),
    CONSTRAINT chk_discussion_turns_verb CHECK (reasoning_verb IN (
        'propose', 'critique', 'summarize_decision'
    )),
    CONSTRAINT chk_discussion_turns_status CHECK (status IN ('claimed', 'recorded', 'failed')),
    -- A recorded turn has a message; a claimed one does not yet.
    CONSTRAINT chk_discussion_turns_recorded CHECK (
        (status = 'recorded') = (message_id IS NOT NULL)
    ),
    -- THE execution-ownership authority: one canonical turn per slot, forever.
    CONSTRAINT uq_discussion_turns_slot UNIQUE (discussion_id, round_index, seat_index),
    -- One reasoning attempt per slot, independently of the slot claim.
    CONSTRAINT uq_discussion_turns_correlation UNIQUE (correlation_id)
);

CREATE INDEX IF NOT EXISTS idx_discussion_turns_discussion
    ON discussion_turns (discussion_id, round_index, seat_index);
CREATE INDEX IF NOT EXISTS idx_discussion_turns_message
    ON discussion_turns (message_id);

-- ---------------------------------------------------------------------
-- 4. Terminal immutability.
--    A closed discussion is evidence. Reopening one, or rewriting why it stopped, would destroy
--    the record of what the team was working from -- the same reasoning plan_revisions applies to
--    an accepted revision. Counters and cursor are frozen at closure too, so a late writer cannot
--    make a closed discussion look like it ran longer than it did.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION discussion_sessions_enforce_terminal() RETURNS TRIGGER AS $$
BEGIN
    IF OLD.state <> 'open' THEN
        IF NEW.state         IS DISTINCT FROM OLD.state
        OR NEW.stop_reason   IS DISTINCT FROM OLD.stop_reason
        OR NEW.current_round IS DISTINCT FROM OLD.current_round
        OR NEW.turns_taken   IS DISTINCT FROM OLD.turns_taken
        OR NEW.messages_posted     IS DISTINCT FROM OLD.messages_posted
        OR NEW.invocations_started IS DISTINCT FROM OLD.invocations_started
        OR NEW.result_message_id   IS DISTINCT FROM OLD.result_message_id
        OR NEW.closed_at     IS DISTINCT FROM OLD.closed_at THEN
            RAISE EXCEPTION
                'discussion % is terminal (%/%) and may not be reopened or rewritten',
                OLD.discussion_id, OLD.state, OLD.stop_reason
                USING ERRCODE = 'restrict_violation';
        END IF;
    END IF;

    -- Bounds are set once, at open. Raising a limit mid-flight would make "bounded" meaningless.
    IF NEW.max_rounds                IS DISTINCT FROM OLD.max_rounds
    OR NEW.max_messages              IS DISTINCT FROM OLD.max_messages
    OR NEW.max_invocations           IS DISTINCT FROM OLD.max_invocations
    OR NEW.max_turns_per_participant IS DISTINCT FROM OLD.max_turns_per_participant THEN
        RAISE EXCEPTION
            'discussion % may not have its bounds changed after it was opened', OLD.discussion_id
            USING ERRCODE = 'restrict_violation';
    END IF;

    -- Subject matter is what the discussion is ABOUT. Changing it mid-flight would silently
    -- re-point every message already recorded under it.
    IF NEW.discussion_id    IS DISTINCT FROM OLD.discussion_id
    OR NEW.project_id       IS DISTINCT FROM OLD.project_id
    OR NEW.goal_id          IS DISTINCT FROM OLD.goal_id
    OR NEW.plan_revision_id IS DISTINCT FROM OLD.plan_revision_id
    OR NEW.thread_id        IS DISTINCT FROM OLD.thread_id
    OR NEW.topic            IS DISTINCT FROM OLD.topic
    OR NEW.required_capabilities IS DISTINCT FROM OLD.required_capabilities
    OR NEW.opened_by        IS DISTINCT FROM OLD.opened_by
    OR NEW.idempotency_key  IS DISTINCT FROM OLD.idempotency_key
    OR NEW.created_at       IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION
            'discussion % may not have its subject or identity updated in place', OLD.discussion_id
            USING ERRCODE = 'restrict_violation';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_discussion_sessions_terminal ON discussion_sessions;
CREATE TRIGGER trg_discussion_sessions_terminal
    BEFORE UPDATE ON discussion_sessions
    FOR EACH ROW EXECUTE FUNCTION discussion_sessions_enforce_terminal();

-- ---------------------------------------------------------------------
-- 5. Turn ledger append-only-ness.
--    A recorded turn is what a participant said and when. Only the claimed -> recorded|failed
--    completion is writable; the slot, speaker, correlation and message are not.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION discussion_turns_enforce_append_only() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.turn_id              IS DISTINCT FROM OLD.turn_id
    OR NEW.discussion_id        IS DISTINCT FROM OLD.discussion_id
    OR NEW.round_index          IS DISTINCT FROM OLD.round_index
    OR NEW.seat_index           IS DISTINCT FROM OLD.seat_index
    OR NEW.speaker_principal_id IS DISTINCT FROM OLD.speaker_principal_id
    OR NEW.correlation_id       IS DISTINCT FROM OLD.correlation_id
    OR NEW.created_at           IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION
            'discussion turn % may not have its slot, speaker or correlation rewritten',
            OLD.turn_id
            USING ERRCODE = 'restrict_violation';
    END IF;

    IF OLD.status <> 'claimed' AND (
        NEW.status     IS DISTINCT FROM OLD.status
     OR NEW.message_id IS DISTINCT FROM OLD.message_id
     OR NEW.intent     IS DISTINCT FROM OLD.intent
    ) THEN
        RAISE EXCEPTION
            'discussion turn % is already %; its outcome may not be rewritten',
            OLD.turn_id, OLD.status
            USING ERRCODE = 'restrict_violation';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_discussion_turns_append_only ON discussion_turns;
CREATE TRIGGER trg_discussion_turns_append_only
    BEFORE UPDATE ON discussion_turns
    FOR EACH ROW EXECUTE FUNCTION discussion_turns_enforce_append_only();

COMMIT;
