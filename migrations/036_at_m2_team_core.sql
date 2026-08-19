-- Step AT-M2-TEAM-CORE -- runtime team identity, addressed collaboration and capability routing.
--
-- ADDITIVE ONLY. Creates the AT-M1 L2 collaboration entities as runtime tables for the first
-- time: actor_principals, agent_profiles, project_team_memberships, conversation_threads,
-- team_messages, team_decisions, agent_handoffs, plus the routing evidence table
-- agent_routing_decisions. It adds no column to any existing table, renames nothing, drops
-- nothing and backfills nothing.
--
-- CANONICAL SEMANTICS (docs/architecture/autonomous-team/actor-principal-and-team-model.md and
-- collaboration-and-workroom-model.md):
--   * There is deliberately NO `teams` table. A team IS the set of active
--     project_team_memberships for a project, exactly as the contract defines it. Introducing a
--     team aggregate here would create a second identity model parallel to the AT-M1 contract.
--   * actor_principals is NOT the task/authorization Actor. That Actor already owns the name
--     `principal_id` in the two-person-control domain (shared/sdk/tasks) and is an AUTHORIZATION
--     subject. This table is the attribution subject for team collaboration. The two are not
--     joined, not merged, and neither is migrated onto the other (AT-D02).
--   * agent_handoffs is NOT delivery_packages handoff_summaries. That legacy name is a delivery
--     DOCUMENT SECTION with no from/to principal and no transfer state.
--   * TASK_ROLES is untouched. No runtime agent principal acquires a human authorization role
--     (INV-01), and nothing here grants authorization -- routing selects a worker, it never
--     approves an action.
--   * Execution lineage is unchanged (AT-D01 / INV-02): Project -> Work Item -> Run remains the
--     sole autonomous execution lineage. Nothing below is an execution record.
--
-- STORAGE PROHIBITION (AT-D03 R8 / INV-04): no column in this migration holds hidden reasoning.
-- Only conclusions a principal stands behind are durable: summary, content, rationale_summary,
-- dissent_summary, reason. No prompt, no reasoning trace, no token trace, no credential value.
-- Bodies are plain TEXT/JSONB, length-limited at the DB layer alongside the Pydantic bounds in
-- shared/sdk/agent_team/models.py, never rendered as HTML and never executed.
--
-- SAFETY: schema only. Starts no container, no workflow, no dispatch and no production action.
-- A routing decision selects a recipient; it does not execute anything and carries no
-- production_effect. Idempotent / re-runnable; a matching *_down.sql reverses it.

BEGIN;

-- 1. Runtime identity -------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS actor_principals (
    principal_id      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    principal_type    TEXT NOT NULL,
    display_name      TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'active',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_actor_principals_type CHECK (principal_type IN (
        'human', 'runtime_agent', 'ai_partner', 'system'
    )),
    CONSTRAINT chk_actor_principals_status CHECK (status IN ('active', 'suspended', 'retired')),
    CONSTRAINT chk_actor_principals_display_name CHECK (length(btrim(display_name)) > 0)
);

CREATE INDEX IF NOT EXISTS idx_actor_principals_type ON actor_principals (principal_type);

-- The functional identity of a runtime agent: what it is FOR, and what it declares it can do.
-- capabilities is the set the router matches against. A declared capability is not permission to
-- exercise it -- tool_policy_profile and the L5 policy boundary still apply.
CREATE TABLE IF NOT EXISTS agent_profiles (
    agent_id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    principal_id          UUID NOT NULL REFERENCES actor_principals(principal_id),
    agent_key             TEXT NOT NULL UNIQUE,
    role                  TEXT NOT NULL,
    capabilities          JSONB NOT NULL DEFAULT '[]'::jsonb,
    -- The stream this agent consumes. Transport only: it says HOW to reach a selected agent,
    -- never WHICH agent is next. The router answers that, from capabilities.
    transport_stream      TEXT,
    -- REFERENCES ONLY. Never a key, token, DSN or any secret VALUE (AT-D02 section 3).
    tool_policy_profile   TEXT,
    model_provider_ref    TEXT,
    status                TEXT NOT NULL DEFAULT 'active',
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_agent_profiles_status CHECK (status IN ('active', 'disabled', 'retired')),
    CONSTRAINT chk_agent_profiles_role CHECK (length(btrim(role)) > 0),
    CONSTRAINT chk_agent_profiles_capabilities CHECK (jsonb_typeof(capabilities) = 'array')
);

CREATE INDEX IF NOT EXISTS idx_agent_profiles_role ON agent_profiles (role);
CREATE INDEX IF NOT EXISTS idx_agent_profiles_capabilities
    ON agent_profiles USING gin (capabilities);

-- 2. Team membership -- the team IS this table, scoped to a project ---------------------------

CREATE TABLE IF NOT EXISTS project_team_memberships (
    membership_id       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id          UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    agent_principal_id  UUID NOT NULL REFERENCES actor_principals(principal_id),
    functional_role     TEXT NOT NULL,
    membership_state    TEXT NOT NULL DEFAULT 'active',
    joined_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Membership is historical: leaving sets left_at rather than deleting the row, so a past
    -- decision by a departed member stays attributable.
    left_at             TIMESTAMPTZ,
    CONSTRAINT chk_ptm_state CHECK (membership_state IN (
        'invited', 'active', 'paused', 'left'
    )),
    CONSTRAINT chk_ptm_role CHECK (length(btrim(functional_role)) > 0),
    CONSTRAINT uq_ptm_project_principal UNIQUE (project_id, agent_principal_id)
);

CREATE INDEX IF NOT EXISTS idx_ptm_project ON project_team_memberships (project_id);
CREATE INDEX IF NOT EXISTS idx_ptm_active
    ON project_team_memberships (project_id, functional_role)
    WHERE membership_state = 'active';

-- 3. Collaboration ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS conversation_threads (
    thread_id      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id     UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    goal_ref       TEXT NOT NULL,
    work_item_id   UUID REFERENCES project_work_items(id) ON DELETE SET NULL,
    run_id         TEXT,
    thread_type    TEXT NOT NULL,
    state          TEXT NOT NULL DEFAULT 'open',
    -- A thread replaced by a later one stays readable with its successor named.
    superseded_by  UUID REFERENCES conversation_threads(thread_id),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_threads_type CHECK (thread_type IN (
        'planning', 'design', 'execution', 'debug', 'blocker', 'clarification',
        'handoff', 'decision'
    )),
    CONSTRAINT chk_threads_state CHECK (state IN (
        'open', 'resolved', 'superseded', 'archived'
    )),
    CONSTRAINT chk_threads_goal_ref CHECK (length(btrim(goal_ref)) > 0)
);

CREATE INDEX IF NOT EXISTS idx_threads_project ON conversation_threads (project_id);

-- An addressed, threaded, durable message between principals. At least one recipient channel is
-- required: an unaddressed message must declare itself a team broadcast rather than be one by
-- omission -- that ambiguity is exactly what makes today's streams uncollaborative.
CREATE TABLE IF NOT EXISTS team_messages (
    message_id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    thread_id               UUID NOT NULL REFERENCES conversation_threads(thread_id)
                                 ON DELETE CASCADE,
    project_id              UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    sender_principal_id     UUID NOT NULL REFERENCES actor_principals(principal_id),
    recipient_principal_id  UUID REFERENCES actor_principals(principal_id),
    recipient_role          TEXT,
    recipient_team          BOOLEAN NOT NULL DEFAULT false,
    parent_message_id       UUID REFERENCES team_messages(message_id),
    message_type            TEXT NOT NULL,
    summary                 TEXT NOT NULL,
    content                 JSONB NOT NULL DEFAULT '{}'::jsonb,
    artifact_refs           JSONB NOT NULL DEFAULT '{}'::jsonb,
    audit_ref               TEXT,
    correlation_id          UUID NOT NULL DEFAULT uuid_generate_v4(),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_team_messages_type CHECK (message_type IN (
        'message', 'proposal', 'challenge', 'decision_summary', 'handoff', 'blocker',
        'clarification_question', 'clarification_answer', 'debug_hypothesis', 'debug_result',
        'replan', 'system_event', 'audit_event'
    )),
    CONSTRAINT chk_team_messages_addressed CHECK (
        recipient_principal_id IS NOT NULL OR recipient_role IS NOT NULL OR recipient_team
    ),
    CONSTRAINT chk_team_messages_summary CHECK (
        length(btrim(summary)) > 0 AND length(summary) <= 2000
    ),
    CONSTRAINT chk_team_messages_content CHECK (jsonb_typeof(content) = 'object')
);

CREATE INDEX IF NOT EXISTS idx_team_messages_thread ON team_messages (thread_id, created_at);
CREATE INDEX IF NOT EXISTS idx_team_messages_recipient
    ON team_messages (recipient_principal_id, created_at);
CREATE INDEX IF NOT EXISTS idx_team_messages_project ON team_messages (project_id, created_at);

-- A coordination choice made BY the team. NOT an Approval (human authorization) and NOT a
-- ProductOwnerDecision (delivery acceptance). The three share no enum and never substitute for
-- one another (INV-03): selected_option is free-form, never a Review Gate Action.
CREATE TABLE IF NOT EXISTS team_decisions (
    decision_id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id                  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    thread_id                   UUID NOT NULL REFERENCES conversation_threads(thread_id)
                                     ON DELETE CASCADE,
    proposed_by                 UUID NOT NULL REFERENCES actor_principals(principal_id),
    options_considered          JSONB NOT NULL DEFAULT '[]'::jsonb,
    selected_option             TEXT NOT NULL,
    rationale_summary           TEXT NOT NULL,
    -- Unresolved objections are RECORDED, never suppressed. A decision that carries its dissent
    -- stays reviewable later, which is the point.
    dissent_summary             TEXT,
    resulting_plan_revision_id  TEXT,
    audit_ref                   TEXT,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_team_decisions_selected CHECK (length(btrim(selected_option)) > 0),
    CONSTRAINT chk_team_decisions_rationale CHECK (length(btrim(rationale_summary)) > 0),
    CONSTRAINT chk_team_decisions_options CHECK (jsonb_typeof(options_considered) = 'array')
);

CREATE INDEX IF NOT EXISTS idx_team_decisions_project ON team_decisions (project_id, created_at);

-- Work transfer between principals. A bare next_owner string cannot express an offer that was
-- declined or a transfer still pending, so ownership moves on 'accepted', never on 'offered'.
CREATE TABLE IF NOT EXISTS agent_handoffs (
    handoff_id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id         UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    work_item_id       UUID REFERENCES project_work_items(id) ON DELETE SET NULL,
    from_principal_id  UUID NOT NULL REFERENCES actor_principals(principal_id),
    to_principal_id    UUID NOT NULL REFERENCES actor_principals(principal_id),
    reason             TEXT NOT NULL,
    context_refs       JSONB NOT NULL DEFAULT '{}'::jsonb,
    state              TEXT NOT NULL DEFAULT 'offered',
    audit_ref          TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    accepted_at        TIMESTAMPTZ,
    CONSTRAINT chk_handoffs_state CHECK (state IN (
        'offered', 'accepted', 'declined', 'withdrawn', 'expired'
    )),
    CONSTRAINT chk_handoffs_reason CHECK (length(btrim(reason)) > 0),
    CONSTRAINT chk_handoffs_distinct CHECK (from_principal_id <> to_principal_id)
);

CREATE INDEX IF NOT EXISTS idx_handoffs_project ON agent_handoffs (project_id, created_at);

-- 4. Routing evidence --------------------------------------------------------------------------
-- Why the runtime chose this successor. Durable because "the router picked qa-agent" is only
-- reviewable if the eligible set and the rejection reasons survive with it. A row with
-- selected_principal_id NULL and outcome 'no_eligible_agent' is the honest answer when the team
-- has nobody who can do the work -- it is never a fallback to a compile-time successor.
CREATE TABLE IF NOT EXISTS agent_routing_decisions (
    routing_decision_id     UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id              UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    work_item_id            UUID REFERENCES project_work_items(id) ON DELETE SET NULL,
    task_id                 TEXT,
    workflow_id             TEXT,
    requested_capability    TEXT NOT NULL,
    outcome                 TEXT NOT NULL,
    selected_principal_id   UUID REFERENCES actor_principals(principal_id),
    selected_role           TEXT,
    selected_stream         TEXT,
    reason                  TEXT NOT NULL,
    candidates_considered   JSONB NOT NULL DEFAULT '[]'::jsonb,
    policy_ref              TEXT,
    audit_ref               TEXT,
    correlation_id          UUID NOT NULL DEFAULT uuid_generate_v4(),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_routing_outcome CHECK (outcome IN (
        'selected', 'no_eligible_agent', 'requires_human_approval'
    )),
    CONSTRAINT chk_routing_selected_consistency CHECK (
        (outcome = 'selected' AND selected_principal_id IS NOT NULL)
        OR (outcome <> 'selected' AND selected_principal_id IS NULL)
    ),
    CONSTRAINT chk_routing_capability CHECK (length(btrim(requested_capability)) > 0),
    CONSTRAINT chk_routing_reason CHECK (length(btrim(reason)) > 0),
    CONSTRAINT chk_routing_candidates CHECK (jsonb_typeof(candidates_considered) = 'array')
);

CREATE INDEX IF NOT EXISTS idx_routing_project ON agent_routing_decisions (project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_routing_capability
    ON agent_routing_decisions (requested_capability, created_at);

COMMIT;
