-- Step 66C.4-BE3-R1 (finding M-1 closure) -- production-action approval registry.
--
-- ADDITIVE ONLY. Creates one new table (production_action_approvals) that is the AUTHORITATIVE
-- source resolved by resume_replay_authorizations.production_approval_reference at consume time
-- (Step 66C.4-BE3-R combined review finding M-1: the reference was previously checked only for
-- non-emptiness). Design decided in be3-r1-m1-production-approval-contract.md and the operator's
-- 2026-07-28 decisions: RESOURCE-scoped (same resource_type/resource_id as the bound resume/replay
-- authorization -- NOT task-scoped), SINGLE-USE (consumed exactly once, alongside exactly one
-- authorization consume), same 1s-24h validity bound as every other BE3 request/authorization. It
-- does NOT touch any existing table, adds no column to an existing table, and performs no backfill.
--
-- SAFETY (Step 66C.4-BE3-R1): this migration creates schema only. It wires up NO HTTP endpoint (no
-- grant/revoke API in this stage -- see the contract record §2.8), NO resume/replay execution, NO
-- scheduler. Approvals may be granted/revoked/resolved only via the internal service (tests only in
-- this stage). Idempotent / re-runnable. A matching *_down.sql reverses it.
--
-- The approval is: resource-bound (same resource_type/resource_id as the resume/replay
-- authorization it backs), action-bound, team/project-bound, single-use (consumed_at), time-bounded
-- (expires_at), state-version-bound (resource_state_version -- an independent snapshot, re-validated
-- at resolve time, giving defense-in-depth alongside the authorization's own CAS), and revocable
-- before consumption (revoked_at). Approver roles are the canonical TASK_ROLES
-- {reviewer_approver, platform_admin} -- the SAME pair already used for replay's Approver role (the
-- "Approve / reject gated action" row of docs/test/ai-team-work-rbac-blueprint.md §3). No second
-- RBAC system. No raw clarification/answer/replay payload/secret/DSN is ever stored here.

BEGIN;

CREATE TABLE IF NOT EXISTS production_action_approvals (
    approval_id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    action_type              TEXT NOT NULL,                -- 'resume' | 'replay' (same vocabulary as
                                                             -- resume_replay_authorizations)
    resource_type            TEXT NOT NULL,                -- 'clarification' | 'outbox_event'
    -- SAME resource as the resume/replay authorization this approval is meant to back (operator
    -- decision, 2026-07-28: resource-scoped, not task-scoped). No FK is declared, for the identical
    -- reason resume_replay_authorizations.resource_id has none: resource_id is polymorphic across
    -- two different owning tables depending on resource_type.
    resource_id               UUID NOT NULL,
    team_id                   UUID NOT NULL,
    project_id                UUID NOT NULL,
    -- Independent snapshot of the resource's state-version at GRANT time, re-validated at resolve
    -- time against the caller-supplied CURRENT version (defense-in-depth alongside the bound
    -- authorization's own resource_state_version CAS -- see production_approval_repository.py).
    resource_state_version    TEXT NOT NULL,

    state                     TEXT NOT NULL DEFAULT 'granted',   -- granted|revoked|consumed
    granted_by                TEXT NOT NULL,
    granted_role              TEXT NOT NULL,
    granted_at                TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
    reason_code               TEXT,

    expires_at                TIMESTAMPTZ NOT NULL,

    consumed_at                    TIMESTAMPTZ,
    consumed_by                    TEXT,
    -- The ONE resume/replay authorization this approval was consumed alongside (set atomically with
    -- consumed_at). Lets an auditor trace "which resume/replay attempt actually used this sign-off"
    -- without ever storing the underlying business content.
    consumed_by_authorization_id   UUID REFERENCES resume_replay_authorizations(authorization_id),

    revoked_at                TIMESTAMPTZ,
    revoked_by                 TEXT,
    revocation_reason_code    TEXT,

    idempotency_key            TEXT NOT NULL,
    created_at                 TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
    updated_at                 TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),

    CONSTRAINT uq_paa_idempotency_key UNIQUE (idempotency_key),
    CONSTRAINT chk_paa_action_type CHECK (action_type IN ('resume', 'replay')),
    CONSTRAINT chk_paa_resource_type CHECK (resource_type IN ('clarification', 'outbox_event')),
    CONSTRAINT chk_paa_state CHECK (state IN ('granted', 'revoked', 'consumed')),
    -- time-bounded: an approval must expire strictly after it was granted.
    CONSTRAINT chk_paa_expiry_after_grant CHECK (expires_at > granted_at),
    -- consumed/revoked timestamp <-> actor coherence.
    CONSTRAINT chk_paa_consumed_coherent CHECK ((consumed_at IS NULL) = (consumed_by IS NULL)),
    CONSTRAINT chk_paa_revoked_coherent CHECK ((revoked_at IS NULL) = (revoked_by IS NULL)),
    -- state must agree with which timestamp (if any) is set.
    CONSTRAINT chk_paa_consumed_requires_state CHECK (consumed_at IS NULL OR state = 'consumed'),
    CONSTRAINT chk_paa_revoked_requires_state CHECK (revoked_at IS NULL OR state = 'revoked'),
    -- an approval can never be both consumed and revoked.
    CONSTRAINT chk_paa_not_consumed_and_revoked CHECK (consumed_at IS NULL OR revoked_at IS NULL),
    -- bounded, secret-free labels.
    CONSTRAINT chk_paa_reason_code_bounded CHECK (
        reason_code IS NULL OR length(reason_code) <= 64
    ),
    CONSTRAINT chk_paa_revocation_reason_bounded CHECK (
        revocation_reason_code IS NULL OR length(revocation_reason_code) <= 64
    ),
    CONSTRAINT chk_paa_state_version_nonempty CHECK (length(btrim(resource_state_version)) > 0),
    CONSTRAINT chk_paa_granted_by_bounded CHECK (length(granted_by) <= 128),
    CONSTRAINT chk_paa_idempotency_key_bounded CHECK (length(idempotency_key) BETWEEN 1 AND 256),
    CONSTRAINT chk_paa_idempotency_key_nonempty CHECK (length(btrim(idempotency_key)) > 0)
);

-- Team/project/resource/action isolation scans and resolution lookups.
CREATE INDEX IF NOT EXISTS idx_paa_scope
    ON production_action_approvals (team_id, project_id, resource_type, resource_id);

-- Resolution by authorization (audit trace of which approval backed which consume).
CREATE INDEX IF NOT EXISTS idx_paa_consumed_by_authorization
    ON production_action_approvals (consumed_by_authorization_id)
    WHERE consumed_by_authorization_id IS NOT NULL;

COMMIT;
