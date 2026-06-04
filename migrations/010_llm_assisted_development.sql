-- 010_llm_assisted_development.sql
-- Stage 30 — LLM-assisted development planning + safety guardrails.
--
-- Three new tables capture: (1) one row per LLM call (prompt hash +
-- redacted preview + response hash + redacted preview + safety
-- result), (2) one row per LLM proposal artifact (file changes that
-- still need policy + human review before they can enter a
-- code_workspace), and (3) one row per token / cost record so the
-- platform can prove zero-real-call by default.
--
-- Strictly additive + idempotent. Existing tables
-- (code_workspaces, code_change_artifacts, pr_draft_artifacts,
-- qa_validation_runs, qa_findings, auto_fix_requests, task_work_items,
-- workflow_states, audit_logs, …) are untouched.

BEGIN;

-- ---------------------------------------------------------------------
-- 1. llm_interactions — one row per LLM call.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS llm_interactions (
    interaction_id    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id           TEXT NOT NULL,
    workflow_id       TEXT,
    provider          TEXT NOT NULL DEFAULT 'mock',
    model_name        TEXT NOT NULL DEFAULT 'mock-deterministic',
    interaction_type  TEXT NOT NULL DEFAULT 'development_plan',
    prompt_hash       TEXT NOT NULL DEFAULT '',
    prompt_preview    TEXT NOT NULL DEFAULT '',
    response_hash     TEXT NOT NULL DEFAULT '',
    response_preview  TEXT NOT NULL DEFAULT '',
    status            TEXT NOT NULL DEFAULT 'ok',
    token_usage       JSONB,
    safety_result     JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_llm_interactions_task_id
    ON llm_interactions (task_id);
CREATE INDEX IF NOT EXISTS idx_llm_interactions_interaction_type
    ON llm_interactions (interaction_type);
CREATE INDEX IF NOT EXISTS idx_llm_interactions_provider
    ON llm_interactions (provider);
CREATE INDEX IF NOT EXISTS idx_llm_interactions_created_at
    ON llm_interactions (created_at DESC);

-- ---------------------------------------------------------------------
-- 2. llm_proposal_artifacts — one row per proposed patch / plan.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS llm_proposal_artifacts (
    proposal_id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id                TEXT NOT NULL,
    workflow_id            TEXT,
    interaction_id         UUID,
    proposal_type          TEXT NOT NULL DEFAULT 'patch_proposal',
    status                 TEXT NOT NULL DEFAULT 'proposed',
    proposed_files         JSONB NOT NULL DEFAULT '[]'::jsonb,
    plan                   JSONB NOT NULL DEFAULT '{}'::jsonb,
    safety_result          JSONB NOT NULL DEFAULT '{}'::jsonb,
    requires_human_review  BOOLEAN NOT NULL DEFAULT TRUE,
    linked_workspace_id    UUID,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_llm_proposal_artifacts_task_id
    ON llm_proposal_artifacts (task_id);
CREATE INDEX IF NOT EXISTS idx_llm_proposal_artifacts_status
    ON llm_proposal_artifacts (status);
CREATE INDEX IF NOT EXISTS idx_llm_proposal_artifacts_proposal_type
    ON llm_proposal_artifacts (proposal_type);
CREATE INDEX IF NOT EXISTS idx_llm_proposal_artifacts_created_at
    ON llm_proposal_artifacts (created_at DESC);

-- ---------------------------------------------------------------------
-- 3. llm_usage_records — token / cost ledger. Mock provider = 0.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS llm_usage_records (
    usage_id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id            TEXT NOT NULL,
    provider           TEXT NOT NULL DEFAULT 'mock',
    model_name         TEXT NOT NULL DEFAULT 'mock-deterministic',
    prompt_tokens      INTEGER NOT NULL DEFAULT 0,
    completion_tokens  INTEGER NOT NULL DEFAULT 0,
    total_tokens       INTEGER NOT NULL DEFAULT 0,
    estimated_cost     NUMERIC(12, 6) NOT NULL DEFAULT 0,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_llm_usage_records_task_id
    ON llm_usage_records (task_id);
CREATE INDEX IF NOT EXISTS idx_llm_usage_records_provider
    ON llm_usage_records (provider);
CREATE INDEX IF NOT EXISTS idx_llm_usage_records_created_at
    ON llm_usage_records (created_at DESC);

COMMIT;
