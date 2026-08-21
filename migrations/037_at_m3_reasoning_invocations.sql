-- Step AT-M3.1 -- reasoning contract & provider abstraction: durable invocation metadata.
--
-- ADDITIVE ONLY. Creates exactly one table, reasoning_invocations, which records the METADATA of
-- one reasoning-provider call (propose | critique | summarize_decision). It adds no column to any
-- existing table, renames nothing, drops nothing and backfills nothing.
--
-- SCOPE (AT-D14): this slice is mock/local reasoning only. No row this migration allows ever
-- reflects a real external network call -- provider_mode is constrained to 'mock' and 'disabled'.
-- A future slice that adds a live external provider extends provider_mode; it does not reuse
-- 'mock' or 'disabled' to mean something else.
--
-- STORAGE PROHIBITION (AT-D03 R8 / INV-04, restated for AT-M3): no column below holds a prompt, a
-- completion, hidden reasoning or a credential value. Only call METADATA is durable -- who asked,
-- what verb, which provider/model, how it went, how much it cost. The structured artifact itself
-- (the proposal/critique/decision-summary content) is NOT stored by this table; it is returned to
-- the caller and, in a later slice, becomes TeamMessage.content, which already enforces the same
-- prohibition (shared/sdk/agent_team/models.py::assert_content_is_safe).
--
-- FORWARD REFERENCES: project_id, thread_id and requested_by_principal_id are all NULLABLE. Goal
-- and PlanRevision do not exist yet (AT-M3.2+), so this table names no column for them. A call
-- made before a project/thread exists is still a legitimate, auditable call.
--
-- IDEMPOTENCY: correlation_id is UNIQUE, unlike its AT-M2 cousins on team_messages and
-- agent_routing_decisions (which are per-row trace ids, not caller-supplied dedup keys). Here the
-- caller (the reasoning service) supplies one correlation_id per logical reasoning attempt, and a
-- replayed insert with the same value must resolve to the SAME row rather than a second one --
-- enforced by the UNIQUE constraint, exploited by the store's ON CONFLICT DO NOTHING + re-fetch.
--
-- SAFETY: schema only. Starts no container, no workflow, no dispatch and no production action.
-- production_executed is not a concept this table can express -- a reasoning call selects no
-- worker and executes nothing. Idempotent / re-runnable; a matching *_down.sql reverses it.

BEGIN;

CREATE TABLE IF NOT EXISTS reasoning_invocations (
    invocation_id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id                 UUID REFERENCES projects(id) ON DELETE SET NULL,
    thread_id                  UUID REFERENCES conversation_threads(thread_id) ON DELETE SET NULL,
    requested_by_principal_id  UUID REFERENCES actor_principals(principal_id),
    reasoning_verb              TEXT NOT NULL,
    -- The name the CALLER asked for (e.g. "mock", or a future "external_anthropic"), kept free
    -- text so refusing an unrecognised or not-yet-authorised name never requires a schema change.
    requested_provider_name    TEXT NOT NULL,
    -- The RESOLVED provider class actually used. AT-M3.1 implements exactly two.
    provider_mode               TEXT NOT NULL,
    model_name                  TEXT,
    round_number                 INT NOT NULL DEFAULT 1,
    status                       TEXT NOT NULL,
    failure_category             TEXT,
    failure_reason               TEXT,
    -- A reference to whatever the artifact became downstream (e.g. a message id), once a later
    -- slice exists to create one. Not a foreign key: the referenced table may not exist yet, and
    -- when it does, "reference" is still the honest relationship -- this row is metadata, not the
    -- thing it describes.
    outcome_ref                  TEXT,
    input_tokens                  INT,
    output_tokens                 INT,
    estimated_cost_usd            NUMERIC(12,6),
    latency_ms                    INT,
    correlation_id                 UUID NOT NULL DEFAULT uuid_generate_v4(),
    audit_ref                      TEXT,
    started_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at                    TIMESTAMPTZ,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_reasoning_invocations_correlation UNIQUE (correlation_id),
    CONSTRAINT chk_reasoning_invocations_verb CHECK (reasoning_verb IN (
        'propose', 'critique', 'summarize_decision'
    )),
    CONSTRAINT chk_reasoning_invocations_provider_mode CHECK (provider_mode IN (
        'mock', 'disabled'
    )),
    CONSTRAINT chk_reasoning_invocations_status CHECK (status IN ('succeeded', 'failed')),
    -- A failed call names why; a succeeded one carries no leftover failure text.
    CONSTRAINT chk_reasoning_invocations_status_consistency CHECK (
        (status = 'failed' AND failure_category IS NOT NULL)
        OR (status = 'succeeded' AND failure_category IS NULL AND failure_reason IS NULL)
    ),
    CONSTRAINT chk_reasoning_invocations_failure_category CHECK (
        failure_category IS NULL OR failure_category IN (
            'provider_disabled',
            'provider_unauthorized',
            'malformed_output',
            'content_safety_rejected',
            'provider_unavailable'
        )
    ),
    CONSTRAINT chk_reasoning_invocations_round CHECK (round_number >= 1),
    CONSTRAINT chk_reasoning_invocations_provider_name CHECK (
        length(btrim(requested_provider_name)) > 0
    )
);

CREATE INDEX IF NOT EXISTS idx_reasoning_invocations_project
    ON reasoning_invocations (project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_reasoning_invocations_thread
    ON reasoning_invocations (thread_id, created_at);
CREATE INDEX IF NOT EXISTS idx_reasoning_invocations_status
    ON reasoning_invocations (status, created_at);

COMMIT;
