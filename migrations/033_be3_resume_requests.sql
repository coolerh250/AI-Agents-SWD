-- Step 66C.4-BE3-B -- operator-controlled resume request foundation.
--
-- ADDITIVE ONLY. Creates one new table (resume_requests) that backs the operator-controlled resume
-- request/authorize/gated-execution flow defined in
-- docs/contracts/66c4-reminder-expiry-controlled-resume/be3-resume-replay-state-machine.md and
-- be3-api-event-contract.md. It does NOT touch any existing table, adds no column to an existing
-- table, and performs no backfill, so every pre-existing row and feature is unchanged.
--
-- Authoritative clarification-level markers (resume_eligible_at, resume_requested_at,
-- resume_requested_by, resume_authorized_at) stay on operator_clarification_requests (migration 031)
-- and are NOT duplicated here: this table records the durable REQUEST entity and its own lifecycle
-- (execution_requested/resumed/failed/canceled/expired), which have no clarification-column
-- equivalent. The "one active request per clarification" invariant is enforced BOTH by the
-- operator_clarification_requests.resume_requested_at IS NULL CAS (in the create transaction) and by
-- the uq_rr_active_per_clarification partial unique index here.
--
-- SAFETY (Step 66C.4-BE3-B): schema only. It wires up NO HTTP endpoint by itself, NO orchestrator
-- call, NO resume execution, NO scheduler and NO runtime loop. The durable resume.execution_requested
-- command is a clarification_lifecycle_outbox row (single durable destination), created only by the
-- internal, DISABLED-BY-DEFAULT execution-preparation path. Idempotent / re-runnable. A matching
-- *_down.sql reverses it.
--
-- Scope columns (team_id/project_id) are UUID NOT NULL, matching the Step 66C.4-BE3-A-C2 decision:
-- a resume request is always team- AND project-bound; NULL is never a scope wildcard. workflow_id is
-- nullable because there is no separate workflow entity upstream yet (the task is the resume anchor).

BEGIN;

CREATE TABLE IF NOT EXISTS resume_requests (
    resume_request_id       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    authorization_id        UUID NOT NULL REFERENCES resume_replay_authorizations(authorization_id),
    clarification_id        UUID NOT NULL REFERENCES operator_clarification_requests(id),
    task_id                 UUID NOT NULL REFERENCES operator_tasks(id),
    workflow_id             UUID,                          -- no separate workflow entity yet
    team_id                 UUID NOT NULL,
    project_id              UUID NOT NULL,
    resource_state_version  TEXT NOT NULL,

    state                   TEXT NOT NULL DEFAULT 'authorization_pending',

    requested_by            TEXT NOT NULL,
    requested_at            TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
    authorized_at           TIMESTAMPTZ,
    execution_requested_at  TIMESTAMPTZ,
    resumed_at              TIMESTAMPTZ,
    failed_at               TIMESTAMPTZ,
    canceled_at             TIMESTAMPTZ,
    expired_at              TIMESTAMPTZ,

    command_id              UUID,                          -- the durable outbox command row id
    failure_reason_code     TEXT,

    idempotency_key         TEXT NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),

    CONSTRAINT uq_rr_idempotency_key UNIQUE (idempotency_key),
    CONSTRAINT chk_rr_state CHECK (state IN (
        'authorization_pending', 'authorized', 'execution_pending',
        'resumed', 'rejected', 'canceled', 'failed', 'expired'
    )),
    -- authorized_at is set once the request leaves authorization_pending toward an authorized branch.
    CONSTRAINT chk_rr_authorized_coherent CHECK (
        authorized_at IS NULL
        OR state IN ('authorized', 'execution_pending', 'resumed', 'failed')
    ),
    -- execution_requested_at + command_id appear together only from execution_pending onward.
    CONSTRAINT chk_rr_execution_coherent CHECK (
        (execution_requested_at IS NULL) = (command_id IS NULL)
    ),
    CONSTRAINT chk_rr_execution_state CHECK (
        command_id IS NULL OR state IN ('execution_pending', 'resumed', 'failed')
    ),
    CONSTRAINT chk_rr_resumed_coherent CHECK ((resumed_at IS NULL) OR state = 'resumed'),
    CONSTRAINT chk_rr_failed_coherent CHECK ((failed_at IS NULL) OR state = 'failed'),
    CONSTRAINT chk_rr_canceled_coherent CHECK ((canceled_at IS NULL) OR state = 'canceled'),
    -- bounded, secret-free labels.
    CONSTRAINT chk_rr_failure_reason_bounded CHECK (
        failure_reason_code IS NULL OR length(failure_reason_code) <= 64
    ),
    CONSTRAINT chk_rr_requested_by_bounded CHECK (length(requested_by) <= 128),
    CONSTRAINT chk_rr_state_version_nonempty CHECK (length(btrim(resource_state_version)) > 0),
    CONSTRAINT chk_rr_idempotency_key_bounded CHECK (length(idempotency_key) BETWEEN 1 AND 256),
    CONSTRAINT chk_rr_idempotency_key_nonempty CHECK (length(btrim(idempotency_key)) > 0)
);

-- Only ONE active resume request per clarification. Active set: authorization_pending / authorized /
-- execution_pending. A terminal request (resumed/rejected/canceled/failed/expired) never blocks a new
-- one (recovery is always a NEW request, never an in-place mutation).
CREATE UNIQUE INDEX IF NOT EXISTS uq_rr_active_per_clarification
    ON resume_requests (clarification_id)
    WHERE state IN ('authorization_pending', 'authorized', 'execution_pending');

CREATE INDEX IF NOT EXISTS idx_rr_scope
    ON resume_requests (team_id, project_id, clarification_id);

CREATE INDEX IF NOT EXISTS idx_rr_authorization_id ON resume_requests (authorization_id);
CREATE INDEX IF NOT EXISTS idx_rr_task_id ON resume_requests (task_id);
CREATE INDEX IF NOT EXISTS idx_rr_state ON resume_requests (state);

COMMIT;
