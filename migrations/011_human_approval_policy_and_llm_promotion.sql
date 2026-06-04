-- 011_human_approval_policy_and_llm_promotion.sql
-- Stage 31 -- flexible human approval policy + LLM proposal promotion.
--
-- Four new tables capture:
--   (1) human_approval_policies      -- per-action / per-feature /
--                                       per-stage / delegated authority
--   (2) human_approval_decisions     -- each approve / reject / revoke /
--                                       delegated decision row
--   (3) llm_proposal_approvals       -- per-proposal approval lifecycle
--   (4) llm_proposal_promotions      -- materialised promotion record
--                                       (which proposal entered the
--                                       controlled workspace, under
--                                       which approval / policy)
--
-- Strictly additive + idempotent. Existing tables
-- (llm_interactions, llm_proposal_artifacts, llm_usage_records,
-- code_workspaces, code_change_artifacts, pr_draft_artifacts,
-- qa_validation_runs, qa_findings, auto_fix_requests,
-- task_work_items, workflow_states, audit_logs, ...) are untouched.

BEGIN;

-- ---------------------------------------------------------------------
-- 1. human_approval_policies -- per-task / per-stage / delegated
--    authority granted by a human operator.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS human_approval_policies (
    policy_id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id                TEXT NOT NULL,
    workflow_id            TEXT,
    scope_type             TEXT NOT NULL DEFAULT 'task',
    scope_id               TEXT NOT NULL DEFAULT '',
    approval_mode          TEXT NOT NULL DEFAULT 'per_action',
    status                 TEXT NOT NULL DEFAULT 'pending',
    granted_by             TEXT NOT NULL DEFAULT '',
    granted_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at             TIMESTAMPTZ,
    max_actions            INTEGER,
    max_files_changed      INTEGER,
    max_auto_fix_attempts  INTEGER,
    actions_used           INTEGER NOT NULL DEFAULT 0,
    allowed_stages         JSONB NOT NULL DEFAULT '[]'::jsonb,
    allowed_agents         JSONB NOT NULL DEFAULT '[]'::jsonb,
    allowed_actions        JSONB NOT NULL DEFAULT '[]'::jsonb,
    allowed_paths          JSONB NOT NULL DEFAULT '[]'::jsonb,
    denied_paths           JSONB NOT NULL DEFAULT '[]'::jsonb,
    constraints            JSONB NOT NULL DEFAULT '{}'::jsonb,
    reason                 TEXT,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_human_approval_policies_task_id
    ON human_approval_policies (task_id);
CREATE INDEX IF NOT EXISTS idx_human_approval_policies_status
    ON human_approval_policies (status);
CREATE INDEX IF NOT EXISTS idx_human_approval_policies_approval_mode
    ON human_approval_policies (approval_mode);
CREATE INDEX IF NOT EXISTS idx_human_approval_policies_scope_type
    ON human_approval_policies (scope_type);
CREATE INDEX IF NOT EXISTS idx_human_approval_policies_created_at
    ON human_approval_policies (created_at DESC);

-- ---------------------------------------------------------------------
-- 2. human_approval_decisions -- one row per evaluator decision /
--    explicit approve / reject / revoke event.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS human_approval_decisions (
    decision_id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    policy_id          UUID,
    task_id            TEXT NOT NULL,
    workflow_id        TEXT,
    proposal_id        UUID,
    promotion_id       UUID,
    action_type        TEXT NOT NULL DEFAULT '',
    decision           TEXT NOT NULL DEFAULT 'approved',
    decided_by         TEXT NOT NULL DEFAULT '',
    decided_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    reason             TEXT,
    safety_snapshot    JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_human_approval_decisions_task_id
    ON human_approval_decisions (task_id);
CREATE INDEX IF NOT EXISTS idx_human_approval_decisions_policy_id
    ON human_approval_decisions (policy_id);
CREATE INDEX IF NOT EXISTS idx_human_approval_decisions_decision
    ON human_approval_decisions (decision);
CREATE INDEX IF NOT EXISTS idx_human_approval_decisions_action_type
    ON human_approval_decisions (action_type);
CREATE INDEX IF NOT EXISTS idx_human_approval_decisions_created_at
    ON human_approval_decisions (created_at DESC);

-- ---------------------------------------------------------------------
-- 3. llm_proposal_approvals -- per-proposal approval lifecycle.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS llm_proposal_approvals (
    approval_id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    proposal_id        UUID NOT NULL,
    task_id            TEXT NOT NULL,
    workflow_id        TEXT,
    approval_mode      TEXT NOT NULL DEFAULT 'per_action',
    policy_id          UUID,
    requested_by       TEXT NOT NULL DEFAULT '',
    requested_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    approved_by        TEXT,
    approved_at        TIMESTAMPTZ,
    rejected_by        TEXT,
    rejected_at        TIMESTAMPTZ,
    status             TEXT NOT NULL DEFAULT 'pending',
    reason             TEXT,
    safety_snapshot    JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_llm_proposal_approvals_proposal_id
    ON llm_proposal_approvals (proposal_id);
CREATE INDEX IF NOT EXISTS idx_llm_proposal_approvals_task_id
    ON llm_proposal_approvals (task_id);
CREATE INDEX IF NOT EXISTS idx_llm_proposal_approvals_status
    ON llm_proposal_approvals (status);
CREATE INDEX IF NOT EXISTS idx_llm_proposal_approvals_approval_mode
    ON llm_proposal_approvals (approval_mode);
CREATE INDEX IF NOT EXISTS idx_llm_proposal_approvals_created_at
    ON llm_proposal_approvals (created_at DESC);

-- ---------------------------------------------------------------------
-- 4. llm_proposal_promotions -- the actual conversion event from
--    proposal -> controlled workspace artifacts.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS llm_proposal_promotions (
    promotion_id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    proposal_id         UUID NOT NULL,
    approval_id         UUID,
    policy_id           UUID,
    task_id             TEXT NOT NULL,
    workflow_id         TEXT,
    workspace_id        UUID,
    status              TEXT NOT NULL DEFAULT 'requested',
    promoted_by         TEXT NOT NULL DEFAULT '',
    promoted_at         TIMESTAMPTZ,
    promotion_mode      TEXT NOT NULL DEFAULT 'manual',
    promoted_files      JSONB NOT NULL DEFAULT '[]'::jsonb,
    validation_result   JSONB NOT NULL DEFAULT '{}'::jsonb,
    qa_run_id           UUID,
    pr_draft_id         UUID,
    error               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_llm_proposal_promotions_proposal_id
    ON llm_proposal_promotions (proposal_id);
CREATE INDEX IF NOT EXISTS idx_llm_proposal_promotions_task_id
    ON llm_proposal_promotions (task_id);
CREATE INDEX IF NOT EXISTS idx_llm_proposal_promotions_status
    ON llm_proposal_promotions (status);
CREATE INDEX IF NOT EXISTS idx_llm_proposal_promotions_promotion_mode
    ON llm_proposal_promotions (promotion_mode);
CREATE INDEX IF NOT EXISTS idx_llm_proposal_promotions_created_at
    ON llm_proposal_promotions (created_at DESC);

COMMIT;
