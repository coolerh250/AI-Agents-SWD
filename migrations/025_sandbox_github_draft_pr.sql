-- Step 59 (Stage 61A) -- Sandbox GitHub Draft PR Flow.
--
-- Records each sandbox draft-PR request (dry_run plan or live_sandbox result) with its
-- project / work-item / dispatch / correlation linkage. Idempotent (CREATE TABLE IF NOT
-- EXISTS). A row is a sandbox draft-PR artifact only: NOT a merge, NOT a review, NOT a
-- production approval. No production-execution column; nothing defaults to a write.

CREATE TABLE IF NOT EXISTS sandbox_github_draft_prs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id      UUID REFERENCES projects(id) ON DELETE SET NULL,
    project_key     TEXT,
    work_item_id    UUID REFERENCES project_work_items(id) ON DELETE SET NULL,
    work_item_key   TEXT,
    dispatch_id     TEXT,
    correlation_id  TEXT NOT NULL,
    repository_key  TEXT NOT NULL,
    branch_name     TEXT,
    draft_pr_url    TEXT,
    draft_pr_number INTEGER,
    -- dry_run | live_sandbox
    mode            TEXT NOT NULL DEFAULT 'dry_run',
    -- planned | blocked | created | failed
    status          TEXT NOT NULL DEFAULT 'planned',
    audit_event_id  TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sandbox_draft_prs_project_id
    ON sandbox_github_draft_prs (project_id);
CREATE INDEX IF NOT EXISTS idx_sandbox_draft_prs_work_item_id
    ON sandbox_github_draft_prs (work_item_id);
CREATE INDEX IF NOT EXISTS idx_sandbox_draft_prs_correlation_id
    ON sandbox_github_draft_prs (correlation_id);
CREATE INDEX IF NOT EXISTS idx_sandbox_draft_prs_created_at
    ON sandbox_github_draft_prs (created_at DESC);
