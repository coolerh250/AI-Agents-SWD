-- Step 66C.4-BE3-A -- durable resume/replay authorization foundation.
--
-- ADDITIVE ONLY. Creates one new table (resume_replay_authorizations) that backs the
-- operator-controlled resume and authorized dead-event replay AUTHORIZATION model defined in
-- docs/contracts/66c4-reminder-expiry-controlled-resume/be3-api-event-contract.md. It does NOT
-- touch any existing table, adds no column to an existing table, and performs no backfill, so
-- every pre-existing row and feature is unchanged.
--
-- SAFETY (Step 66C.4-BE3-A): this migration creates schema only. It wires up NO HTTP endpoint,
-- NO resume/replay execution, NO replay_dead caller, NO scheduler and NO runtime loop. The table
-- is a disabled-by-default foundation: authorizations may be requested/approved/consumed only by
-- the internal authorization service (tests only in this stage); consuming an authorization does
-- NOT itself execute resume or replay. Idempotent / re-runnable. A matching *_down.sql reverses it.
--
-- The authorization is: resource-bound, action-bound, team/project-bound, single-use (consumed_at),
-- time-bounded (expires_at), state-version-bound (resource_state_version), and revocable before
-- consumption (revoked_at). Reason codes are bounded, secret-free labels; no raw clarification /
-- answer / replay payload / secret / DSN is ever stored here.

BEGIN;

CREATE TABLE IF NOT EXISTS resume_replay_authorizations (
    authorization_id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    action_type             TEXT NOT NULL,                 -- 'resume' | 'replay'
    resource_type           TEXT NOT NULL,                 -- 'clarification' | 'outbox_event'
    resource_id             UUID NOT NULL,
    -- Scope identifiers compared by equality for isolation. TEXT (not UUID) because there is no
    -- team table upstream and no FK exists on operator_tasks.project_id either; TEXT keeps the
    -- scope model flexible while staying bounded.
    team_id                 TEXT,                          -- nullable: no team column upstream yet
    project_id              TEXT,                          -- from operator_tasks.project_id (as text)
    request_id              UUID NOT NULL DEFAULT uuid_generate_v4(),

    requested_by            TEXT NOT NULL,
    requested_role          TEXT NOT NULL,
    requested_at            TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),

    decision                TEXT NOT NULL DEFAULT 'pending', -- pending|authorized|rejected|canceled
    decided_by              TEXT,
    decided_role            TEXT,
    decided_at              TIMESTAMPTZ,
    decision_reason_code    TEXT,

    policy_result           TEXT,                          -- allow|deny|not_applicable
    policy_version          TEXT,

    resource_state_version  TEXT NOT NULL,
    production_effect       BOOLEAN NOT NULL DEFAULT false,
    production_approval_reference TEXT,                    -- reference to the separate production gate

    expires_at              TIMESTAMPTZ NOT NULL,

    consumed_at             TIMESTAMPTZ,
    consumed_by             TEXT,

    revoked_at              TIMESTAMPTZ,
    revoked_by              TEXT,
    revocation_reason_code  TEXT,

    expired_at              TIMESTAMPTZ,                   -- durable terminal marker set by expire scan

    idempotency_key         TEXT NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),

    CONSTRAINT uq_rra_idempotency_key UNIQUE (idempotency_key),
    CONSTRAINT chk_rra_action_type CHECK (action_type IN ('resume', 'replay')),
    CONSTRAINT chk_rra_resource_type CHECK (resource_type IN ('clarification', 'outbox_event')),
    CONSTRAINT chk_rra_decision CHECK (decision IN ('pending', 'authorized', 'rejected', 'canceled')),
    CONSTRAINT chk_rra_policy_result CHECK (
        policy_result IS NULL OR policy_result IN ('allow', 'deny', 'not_applicable')
    ),
    -- time-bounded: an authorization must expire strictly after it was requested.
    CONSTRAINT chk_rra_expiry_after_request CHECK (expires_at > requested_at),
    -- consumed only when authorized; rejected/canceled/pending can never be consumed.
    CONSTRAINT chk_rra_consume_requires_authorized CHECK (consumed_at IS NULL OR decision = 'authorized'),
    -- revoked only when authorized (a pending is canceled/rejected, not revoked).
    CONSTRAINT chk_rra_revoke_requires_authorized CHECK (revoked_at IS NULL OR decision = 'authorized'),
    -- consumed/revoked timestamp <-> actor coherence.
    CONSTRAINT chk_rra_consumed_coherent CHECK ((consumed_at IS NULL) = (consumed_by IS NULL)),
    CONSTRAINT chk_rra_revoked_coherent CHECK ((revoked_at IS NULL) = (revoked_by IS NULL)),
    -- an authorization can never be both consumed and revoked.
    CONSTRAINT chk_rra_not_consumed_and_revoked CHECK (consumed_at IS NULL OR revoked_at IS NULL),
    -- a decided (non-pending) authorization carries its decider + decision time.
    CONSTRAINT chk_rra_decided_coherent CHECK (
        decision = 'pending' OR (decided_by IS NOT NULL AND decided_at IS NOT NULL)
    ),
    -- requester/approver separation for replay: an AUTHORIZED replay's decider must differ from
    -- the requester (two-person control). Self cancel/reject by the requester is still permitted.
    CONSTRAINT chk_rra_replay_two_person CHECK (
        action_type <> 'replay' OR decision <> 'authorized' OR decided_by <> requested_by
    ),
    -- bounded, secret-free labels.
    CONSTRAINT chk_rra_reason_code_bounded CHECK (
        decision_reason_code IS NULL OR length(decision_reason_code) <= 64
    ),
    CONSTRAINT chk_rra_revocation_reason_bounded CHECK (
        revocation_reason_code IS NULL OR length(revocation_reason_code) <= 64
    ),
    CONSTRAINT chk_rra_state_version_nonempty CHECK (length(btrim(resource_state_version)) > 0),
    CONSTRAINT chk_rra_requested_by_bounded CHECK (length(requested_by) <= 128),
    CONSTRAINT chk_rra_team_id_bounded CHECK (team_id IS NULL OR length(team_id) <= 128),
    CONSTRAINT chk_rra_project_id_bounded CHECK (project_id IS NULL OR length(project_id) <= 128),
    CONSTRAINT chk_rra_idempotency_key_bounded CHECK (length(idempotency_key) BETWEEN 1 AND 256),
    CONSTRAINT chk_rra_idempotency_key_nonempty CHECK (length(btrim(idempotency_key)) > 0)
);

-- Only ONE active request per (action_type, resource_id). Active-state set (documented):
--   decision IN ('pending','authorized') AND NOT consumed AND NOT revoked AND NOT expired.
-- A terminal (rejected/canceled/expired/consumed/revoked) authorization does not block a new request.
CREATE UNIQUE INDEX IF NOT EXISTS uq_rra_active_request
    ON resume_replay_authorizations (action_type, resource_id)
    WHERE decision IN ('pending', 'authorized')
      AND consumed_at IS NULL AND revoked_at IS NULL AND expired_at IS NULL;

-- Authorization lookup by request id.
CREATE INDEX IF NOT EXISTS idx_rra_request_id ON resume_replay_authorizations (request_id);

-- Team/project/resource isolation scans.
CREATE INDEX IF NOT EXISTS idx_rra_scope
    ON resume_replay_authorizations (team_id, project_id, resource_type, resource_id);

-- Expiry scan: unresolved rows whose deadline may have passed.
CREATE INDEX IF NOT EXISTS idx_rra_expiry_scan
    ON resume_replay_authorizations (expires_at)
    WHERE decision IN ('pending', 'authorized')
      AND consumed_at IS NULL AND revoked_at IS NULL AND expired_at IS NULL;

-- Authorized-unconsumed lookup (the consumable set).
CREATE INDEX IF NOT EXISTS idx_rra_authorized_unconsumed
    ON resume_replay_authorizations (action_type, resource_id)
    WHERE decision = 'authorized'
      AND consumed_at IS NULL AND revoked_at IS NULL AND expired_at IS NULL;

COMMIT;
