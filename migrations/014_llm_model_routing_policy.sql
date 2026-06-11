-- 014_llm_model_routing_policy.sql
-- Stage 38 -- LLM Model Routing & Agent Model Policy.
--
-- Three new tables sit BESIDE the existing llm_* + agent tables
-- (none of those are modified):
--
--   (1) llm_model_registry -- catalogue of providers + models the
--       platform may use, with capabilities, schema support, cost,
--       tier, status, and hard-safety flags (plan_only / patch /
--       workspace / production).
--   (2) agent_model_policies -- per (agent, task_type, capability,
--       risk_level) policy: which model_tiers / providers are
--       allowed, preferred / fallback aliases, cost + token caps,
--       human-review requirement, real-LLM allowance, patch +
--       workspace-write allowance. Default-deny: missing policy
--       blocks the routing.
--   (3) llm_routing_decisions -- one row per Model Router call,
--       carrying the routing input + selected (or blocked) outcome.
--       Never carries prompt / response text or API keys.
--
-- Strictly additive + idempotent. Existing tables (audit_logs,
-- audit_integrity_records, llm_interactions, llm_budget_policies,
-- llm_budget_events, code_workspaces, ...) are untouched.

BEGIN;

-- ---------------------------------------------------------------------
-- 1. llm_model_registry -- catalogue of allowed providers + models.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS llm_model_registry (
    model_id                       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    provider                       TEXT NOT NULL,
    model_name                     TEXT NOT NULL,
    model_alias                    TEXT NOT NULL,
    model_tier                     TEXT NOT NULL DEFAULT 'tier_3_documentation_classification',
    capabilities                   JSONB NOT NULL DEFAULT '[]'::jsonb,
    supported_schemas              JSONB NOT NULL DEFAULT '[]'::jsonb,
    max_context_tokens             INTEGER,
    default_max_output_tokens      INTEGER,
    cost_per_1k_input_tokens       NUMERIC(12, 6) DEFAULT 0,
    cost_per_1k_output_tokens      NUMERIC(12, 6) DEFAULT 0,
    latency_class                  TEXT NOT NULL DEFAULT 'standard',
    risk_level                     TEXT NOT NULL DEFAULT 'low',
    status                         TEXT NOT NULL DEFAULT 'active',
    plan_only_allowed              BOOLEAN NOT NULL DEFAULT FALSE,
    patch_generation_allowed       BOOLEAN NOT NULL DEFAULT FALSE,
    workspace_write_allowed        BOOLEAN NOT NULL DEFAULT FALSE,
    production_use_allowed         BOOLEAN NOT NULL DEFAULT FALSE,
    requires_human_review          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at                     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata                       JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT llm_model_registry_alias_unique UNIQUE (model_alias),
    CONSTRAINT llm_model_registry_status_check
        CHECK (status IN ('active', 'inactive', 'deprecated', 'blocked')),
    CONSTRAINT llm_model_registry_tier_check
        CHECK (model_tier IN (
            'tier_1_critical_reasoning',
            'tier_2_development_qa',
            'tier_3_documentation_classification',
            'tier_4_lightweight_embedding'
        ))
);

CREATE INDEX IF NOT EXISTS llm_model_registry_provider_idx
    ON llm_model_registry (provider);
CREATE INDEX IF NOT EXISTS llm_model_registry_status_idx
    ON llm_model_registry (status);
CREATE INDEX IF NOT EXISTS llm_model_registry_tier_idx
    ON llm_model_registry (model_tier);

-- ---------------------------------------------------------------------
-- 2. agent_model_policies -- per (agent, task_type, capability, risk).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_model_policies (
    policy_id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_name                 TEXT NOT NULL,
    task_type                  TEXT NOT NULL DEFAULT 'default',
    capability                 TEXT NOT NULL,
    risk_level                 TEXT NOT NULL DEFAULT 'low',
    preferred_model_alias      TEXT,
    allowed_model_tiers        JSONB NOT NULL DEFAULT '[]'::jsonb,
    allowed_providers          JSONB NOT NULL DEFAULT '[]'::jsonb,
    fallback_model_aliases     JSONB NOT NULL DEFAULT '[]'::jsonb,
    max_cost_per_task_usd      NUMERIC(12, 6),
    max_tokens_per_task        INTEGER,
    requires_human_review      BOOLEAN NOT NULL DEFAULT FALSE,
    allow_real_llm             BOOLEAN NOT NULL DEFAULT FALSE,
    allow_patch_generation     BOOLEAN NOT NULL DEFAULT FALSE,
    allow_workspace_write      BOOLEAN NOT NULL DEFAULT FALSE,
    status                     TEXT NOT NULL DEFAULT 'active',
    created_by                 TEXT NOT NULL DEFAULT 'system',
    created_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata                   JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT agent_model_policies_status_check
        CHECK (status IN ('active', 'inactive', 'deprecated')),
    CONSTRAINT agent_model_policies_risk_check
        CHECK (risk_level IN ('low', 'medium', 'high', 'critical'))
);

CREATE UNIQUE INDEX IF NOT EXISTS agent_model_policies_lookup_unique_idx
    ON agent_model_policies (agent_name, task_type, capability, risk_level)
    WHERE status = 'active';
CREATE INDEX IF NOT EXISTS agent_model_policies_agent_idx
    ON agent_model_policies (agent_name);
CREATE INDEX IF NOT EXISTS agent_model_policies_capability_idx
    ON agent_model_policies (capability);

-- ---------------------------------------------------------------------
-- 3. llm_routing_decisions -- one row per ModelRouter evaluation.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS llm_routing_decisions (
    routing_decision_id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id                        TEXT,
    workflow_id                    TEXT,
    agent_name                     TEXT NOT NULL,
    capability                     TEXT NOT NULL,
    task_type                      TEXT NOT NULL DEFAULT 'default',
    risk_level                     TEXT NOT NULL DEFAULT 'low',
    requested_schema               TEXT,
    requested_model_alias          TEXT,
    selected_provider              TEXT,
    selected_model_name            TEXT,
    selected_model_alias           TEXT,
    selected_model_tier            TEXT,
    decision                       TEXT NOT NULL,
    reason                         TEXT,
    fallback_used                  BOOLEAN NOT NULL DEFAULT FALSE,
    budget_policy_id               UUID,
    estimated_input_tokens         INTEGER,
    estimated_output_tokens        INTEGER,
    estimated_cost_usd             NUMERIC(12, 6),
    requires_human_review          BOOLEAN NOT NULL DEFAULT FALSE,
    real_llm_allowed               BOOLEAN NOT NULL DEFAULT FALSE,
    patch_generation_allowed       BOOLEAN NOT NULL DEFAULT FALSE,
    workspace_write_allowed        BOOLEAN NOT NULL DEFAULT FALSE,
    policy_id                      UUID,
    model_id                       UUID,
    created_at                     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata                       JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT llm_routing_decisions_decision_check
        CHECK (decision IN (
            'selected',
            'mock_selected',
            'fallback_selected',
            'blocked',
            'budget_blocked',
            'schema_unsupported',
            'provider_unavailable',
            'policy_not_found',
            'human_approval_required',
            'direct_model_rejected'
        ))
);

CREATE INDEX IF NOT EXISTS llm_routing_decisions_task_idx
    ON llm_routing_decisions (task_id);
CREATE INDEX IF NOT EXISTS llm_routing_decisions_agent_idx
    ON llm_routing_decisions (agent_name);
CREATE INDEX IF NOT EXISTS llm_routing_decisions_decision_idx
    ON llm_routing_decisions (decision);
CREATE INDEX IF NOT EXISTS llm_routing_decisions_created_idx
    ON llm_routing_decisions (created_at);

COMMIT;
