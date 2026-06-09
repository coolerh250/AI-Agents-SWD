-- 013_llm_cost_governance.sql
-- Stage 35 -- LLM cost governance + real-LLM plan-only pilot.
--
-- Two new tables sit BESIDE the existing llm_* tables (which are not
-- modified):
--
--   (1) llm_budget_policies -- operator-configurable cost caps per
--       scope (global / task / workflow / user / provider). Each
--       policy carries token + cost caps (per-task / per-day /
--       per-month) and an enforcement mode (block / warn_only).
--   (2) llm_budget_events -- one row per preflight + recorded usage
--       + budget_exceeded + budget_warning decision. The policy
--       evaluator writes a row for every gate (allowed / blocked /
--       warning / recorded).
--
-- Strictly additive + idempotent. Existing tables (llm_interactions,
-- llm_proposal_artifacts, llm_usage_records, code_workspaces,
-- code_change_artifacts, audit_logs, audit_integrity_records,
-- ...) are untouched.

BEGIN;

-- ---------------------------------------------------------------------
-- 1. llm_budget_policies -- per-scope cost / token caps.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS llm_budget_policies (
    policy_id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    policy_name            TEXT NOT NULL,
    scope_type             TEXT NOT NULL DEFAULT 'global',
    scope_id               TEXT,
    provider               TEXT NOT NULL DEFAULT 'mock',
    model_name             TEXT,
    max_tokens_per_task    INTEGER,
    max_cost_per_task_usd  NUMERIC(12, 6),
    max_cost_per_day_usd   NUMERIC(12, 6),
    max_cost_per_month_usd NUMERIC(12, 6),
    enforcement_mode       TEXT NOT NULL DEFAULT 'block',
    status                 TEXT NOT NULL DEFAULT 'active',
    created_by             TEXT NOT NULL DEFAULT '',
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata               JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_llm_budget_policies_scope_type
        CHECK (scope_type IN ('global', 'task', 'workflow', 'user', 'provider')),
    CONSTRAINT chk_llm_budget_policies_enforcement_mode
        CHECK (enforcement_mode IN ('block', 'warn_only')),
    CONSTRAINT chk_llm_budget_policies_status
        CHECK (status IN ('active', 'inactive', 'expired'))
);

CREATE INDEX IF NOT EXISTS idx_llm_budget_policies_scope
    ON llm_budget_policies (scope_type, scope_id);
CREATE INDEX IF NOT EXISTS idx_llm_budget_policies_provider
    ON llm_budget_policies (provider);
CREATE INDEX IF NOT EXISTS idx_llm_budget_policies_status
    ON llm_budget_policies (status);
CREATE INDEX IF NOT EXISTS idx_llm_budget_policies_created_at
    ON llm_budget_policies (created_at DESC);

-- ---------------------------------------------------------------------
-- 2. llm_budget_events -- one row per budget decision.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS llm_budget_events (
    budget_event_id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id                   TEXT,
    workflow_id               TEXT,
    policy_id                 UUID REFERENCES llm_budget_policies(policy_id) ON DELETE SET NULL,
    provider                  TEXT NOT NULL DEFAULT 'mock',
    model_name                TEXT NOT NULL DEFAULT '',
    event_type                TEXT NOT NULL,
    estimated_prompt_tokens   INTEGER NOT NULL DEFAULT 0,
    estimated_completion_tokens INTEGER NOT NULL DEFAULT 0,
    estimated_total_tokens    INTEGER NOT NULL DEFAULT 0,
    actual_prompt_tokens      INTEGER,
    actual_completion_tokens  INTEGER,
    actual_total_tokens       INTEGER,
    estimated_cost_usd        NUMERIC(12, 6) NOT NULL DEFAULT 0,
    actual_cost_usd           NUMERIC(12, 6),
    budget_remaining_usd      NUMERIC(12, 6),
    decision                  TEXT NOT NULL,
    reason                    TEXT,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata                  JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_llm_budget_events_event_type
        CHECK (event_type IN (
            'preflight', 'recorded_usage', 'budget_exceeded', 'budget_warning'
        )),
    CONSTRAINT chk_llm_budget_events_decision
        CHECK (decision IN ('allowed', 'blocked', 'warning', 'recorded'))
);

CREATE INDEX IF NOT EXISTS idx_llm_budget_events_task_id
    ON llm_budget_events (task_id);
CREATE INDEX IF NOT EXISTS idx_llm_budget_events_workflow_id
    ON llm_budget_events (workflow_id);
CREATE INDEX IF NOT EXISTS idx_llm_budget_events_policy_id
    ON llm_budget_events (policy_id);
CREATE INDEX IF NOT EXISTS idx_llm_budget_events_provider
    ON llm_budget_events (provider);
CREATE INDEX IF NOT EXISTS idx_llm_budget_events_event_type
    ON llm_budget_events (event_type);
CREATE INDEX IF NOT EXISTS idx_llm_budget_events_decision
    ON llm_budget_events (decision);
CREATE INDEX IF NOT EXISTS idx_llm_budget_events_created_at
    ON llm_budget_events (created_at DESC);

COMMIT;
