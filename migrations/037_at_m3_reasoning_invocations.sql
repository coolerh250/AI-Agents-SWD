-- Step AT-M3.1 -- reasoning contract & provider abstraction: durable invocation metadata.
--
-- ADDITIVE ONLY. Creates exactly one table, reasoning_invocations, which records the METADATA of
-- one reasoning-provider call (propose | critique | summarize_decision). It adds no column to any
-- existing table, renames nothing, drops nothing and backfills nothing.
--
-- Amended for AT-M3.1-REMEDIATION-1 (Validation 1 blocker 1+2): this table is edited IN PLACE
-- rather than superseded by a new migration, because 037 has never been canonical on `main` --
-- it exists only on the unmerged AT-M3.1 branch, so there is no historical state to preserve
-- separately from this correction (unlike an AT-M2 table, which is off-limits once merged).
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
-- LIFECYCLE (Validation 1 blocker 1+2 fix): a row is durably INSERTED in status='started' BEFORE
-- the provider is ever called -- ownership of a correlation_id is claimed by that atomic insert
-- (UNIQUE + ON CONFLICT DO NOTHING), not decided by a prior SELECT. The provider only runs for the
-- caller that won the insert. The row then transitions started -> succeeded|failed via an UPDATE
-- guarded by `WHERE status='started'`, so a terminal row can never be overwritten and a duplicate
-- caller that lost the claim never gets to invoke the provider at all. If that terminal UPDATE
-- itself fails (a dropped connection, for example), the STARTED row -- inserted before the
-- provider ran -- remains as durable evidence that the attempt occurred; nothing here silently
-- loses it. Recovering a permanently-stranded STARTED row (its owner crashed and never returned)
-- is explicitly deferred -- no lease/takeover mechanism is added by this slice.
--
-- FORWARD REFERENCES: project_id, thread_id and requested_by_principal_id are all NULLABLE. Goal
-- and PlanRevision do not exist yet (AT-M3.2+), so this table names no column for them. A call
-- made before a project/thread exists is still a legitimate, auditable call.
--
-- IDEMPOTENCY: correlation_id is UNIQUE, unlike its AT-M2 cousins on team_messages and
-- agent_routing_decisions (which are per-row trace ids, not caller-supplied dedup keys). Here the
-- caller (the reasoning service) supplies one correlation_id per logical reasoning attempt. The
-- UNIQUE constraint is the single execution-ownership authority: exactly one concurrent caller's
-- INSERT ... ON CONFLICT DO NOTHING wins per correlation_id, and every other caller (whether it
-- arrives before or after the winner's terminal update) observes the SAME row rather than racing
-- its own provider call.
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
    -- started: durably claimed, provider has not yet returned a terminal outcome.
    -- succeeded / failed: terminal, reachable only from 'started' (enforced by the store's
    -- UPDATE ... WHERE status='started', not by this constraint alone).
    status                       TEXT NOT NULL DEFAULT 'started',
    failure_category             TEXT,
    -- Never the raw provider/exception text verbatim -- sanitized before it ever reaches this
    -- column (shared/sdk/agent_reasoning/models.py::sanitize_failure_reason), applied at BOTH the
    -- service layer and here at the store layer, mirroring TeamStore.post_message's own
    -- defense-in-depth for content/artifact_refs ("callers build a plain dict, so the model
    -- validator alone would leave the prohibition bypassable by construction").
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
    -- When this attempt was claimed (the INSERT), never when it was created for bookkeeping
    -- purposes only -- there is no other kind of row here.
    started_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- NULL while status='started'; set exactly once, by the terminal UPDATE.
    completed_at                    TIMESTAMPTZ,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_reasoning_invocations_correlation UNIQUE (correlation_id),
    CONSTRAINT chk_reasoning_invocations_verb CHECK (reasoning_verb IN (
        'propose', 'critique', 'summarize_decision'
    )),
    CONSTRAINT chk_reasoning_invocations_provider_mode CHECK (provider_mode IN (
        'mock', 'disabled'
    )),
    CONSTRAINT chk_reasoning_invocations_status CHECK (status IN (
        'started', 'succeeded', 'failed'
    )),
    -- started: no failure text, not yet completed. succeeded: no leftover failure text, and
    -- completed. failed: names why, and completed. No other combination is representable.
    CONSTRAINT chk_reasoning_invocations_status_consistency CHECK (
        (status = 'started'
            AND failure_category IS NULL AND failure_reason IS NULL AND completed_at IS NULL)
        OR (status = 'succeeded'
            AND failure_category IS NULL AND failure_reason IS NULL AND completed_at IS NOT NULL)
        OR (status = 'failed'
            AND failure_category IS NOT NULL AND completed_at IS NOT NULL)
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
