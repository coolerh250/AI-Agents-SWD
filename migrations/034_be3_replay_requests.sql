-- Step 66C.4-BE3-C -- authorized dead-event replay request foundation.
--
-- ADDITIVE ONLY. Creates one new table (replay_requests) that backs the two-person-controlled
-- dead-event replay request/authorize/gated-execution flow defined in
-- docs/contracts/66c4-reminder-expiry-controlled-resume/be3-resume-replay-state-machine.md and
-- be3-api-event-contract.md. It does NOT touch clarification_lifecycle_outbox (031),
-- resume_replay_authorizations (032), or resume_requests (033); adds no column to any existing
-- table; performs no backfill. Every pre-existing row and feature is unchanged.
--
-- Resource-state-version decision (Step 66C.4-BE3-C, recorded in
-- be3-c-authorized-dead-event-replay-record.md): rather than adding a new monotonic version column
-- to the already-merged clarification_lifecycle_outbox table, a replay request snapshots
-- f"{dead_at.isoformat()}:{attempts}" as its resource_state_version. dead_at is set EXACTLY ONCE per
-- distinct "became dead" episode (never touched while a row is 'pending', cleared to NULL only on
-- replay) and attempts is frozen the moment a row goes dead (the relay's pending-only claim query
-- never touches a 'dead' row), so this composite uniquely and durably identifies "this exact dead
-- episode" without any new column. Re-validated at authorize and execute time under a row lock.
--
-- SAFETY (Step 66C.4-BE3-C): schema only. Wires up NO HTTP endpoint, NO real replay_dead call in
-- any shared runtime, NO scheduler, NO consumer activation. replay_requests may be
-- requested/approved/consumed only via the internal service (tests only in this stage); a durable
-- authorization consumption here does NOT itself publish anything downstream -- the existing BE2
-- audit relay (unchanged, still disabled in every shared runtime) is the only thing that ever
-- publishes a row, on its own later cycle. Idempotent / re-runnable. A matching *_down.sql reverses.

BEGIN;

CREATE TABLE IF NOT EXISTS replay_requests (
    replay_request_id       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    authorization_id        UUID NOT NULL REFERENCES resume_replay_authorizations(authorization_id),
    outbox_event_id         UUID NOT NULL REFERENCES clarification_lifecycle_outbox(id),
    event_type              TEXT NOT NULL,                 -- snapshot at request time
    destination             TEXT NOT NULL,                 -- snapshot of destination_for_event_type
    team_id                 UUID NOT NULL,                 -- actor-declared (no team table upstream)
    project_id              UUID NOT NULL,                 -- cross-checked against the owning task
    resource_state_version  TEXT NOT NULL,                 -- f"{dead_at}:{attempts}" snapshot

    state                   TEXT NOT NULL DEFAULT 'authorization_pending',

    requested_by            TEXT NOT NULL,
    requested_at            TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
    authorized_at           TIMESTAMPTZ,
    executed_at             TIMESTAMPTZ,
    rejected_at             TIMESTAMPTZ,
    canceled_at             TIMESTAMPTZ,
    expired_at              TIMESTAMPTZ,
    failure_reason_code     TEXT,

    idempotency_key         TEXT NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),

    CONSTRAINT uq_rpr_idempotency_key UNIQUE (idempotency_key),
    CONSTRAINT chk_rpr_state CHECK (state IN (
        'authorization_pending', 'authorized', 'executed',
        'rejected', 'canceled', 'expired', 'failed'
    )),
    CONSTRAINT chk_rpr_event_type_nonempty CHECK (length(btrim(event_type)) > 0),
    CONSTRAINT chk_rpr_destination_nonempty CHECK (length(btrim(destination)) > 0),
    CONSTRAINT chk_rpr_authorized_coherent CHECK (
        authorized_at IS NULL OR state IN ('authorized', 'executed', 'failed')
    ),
    CONSTRAINT chk_rpr_executed_coherent CHECK ((executed_at IS NULL) OR state = 'executed'),
    CONSTRAINT chk_rpr_rejected_coherent CHECK ((rejected_at IS NULL) OR state = 'rejected'),
    CONSTRAINT chk_rpr_canceled_coherent CHECK ((canceled_at IS NULL) OR state = 'canceled'),
    CONSTRAINT chk_rpr_expired_coherent CHECK ((expired_at IS NULL) OR state = 'expired'),
    CONSTRAINT chk_rpr_failure_reason_bounded CHECK (
        failure_reason_code IS NULL OR length(failure_reason_code) <= 64
    ),
    CONSTRAINT chk_rpr_requested_by_bounded CHECK (length(requested_by) <= 128),
    CONSTRAINT chk_rpr_state_version_nonempty CHECK (length(btrim(resource_state_version)) > 0),
    CONSTRAINT chk_rpr_idempotency_key_bounded CHECK (length(idempotency_key) BETWEEN 1 AND 256),
    CONSTRAINT chk_rpr_idempotency_key_nonempty CHECK (length(btrim(idempotency_key)) > 0)
);

-- Only ONE active replay request per outbox event. Active set: authorization_pending / authorized.
-- A terminal request (executed/rejected/canceled/expired/failed) never blocks a new one (recovery is
-- always a NEW request, never an in-place mutation) -- matching the resume_requests convention.
CREATE UNIQUE INDEX IF NOT EXISTS uq_rpr_active_per_event
    ON replay_requests (outbox_event_id)
    WHERE state IN ('authorization_pending', 'authorized');

CREATE INDEX IF NOT EXISTS idx_rpr_scope
    ON replay_requests (team_id, project_id, outbox_event_id);

CREATE INDEX IF NOT EXISTS idx_rpr_authorization_id ON replay_requests (authorization_id);
CREATE INDEX IF NOT EXISTS idx_rpr_outbox_event_id ON replay_requests (outbox_event_id);
CREATE INDEX IF NOT EXISTS idx_rpr_state ON replay_requests (state);

-- Rate-limit support: bounded successful replays per event within a window, and bounded requests
-- per actor within a window (read-only COUNT queries; no new column/table needed).
CREATE INDEX IF NOT EXISTS idx_rpr_requested_by_requested_at
    ON replay_requests (requested_by, requested_at);

CREATE INDEX IF NOT EXISTS idx_rpr_event_executed_at
    ON replay_requests (outbox_event_id, executed_at) WHERE state = 'executed';

COMMIT;
