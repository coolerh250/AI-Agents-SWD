-- 017_project_planner_task_graph.sql
-- Stage 45 -- Project Planner & Task Graph Orchestration.
--
-- Strictly additive + idempotent. Adds the project-planning data model that
-- sits BESIDE the existing workflow tables (tasks, workflow_states,
-- agent_executions, task_work_items, audit_logs, ...) -- none of which are
-- modified. This is the foundation for moving the platform from a linear
-- workflow pipeline to a project/task-graph delivery platform.
--
-- Ten tables:
--   projects                          -- parent project per user request
--   project_briefs                    -- problem/goal/scope/non-scope/...
--   project_user_stories              -- actor/need/benefit user stories
--   project_acceptance_criteria       -- verifiable acceptance criteria
--   project_milestones                -- ordered delivery milestones
--   project_work_items                -- schedulable work items (graph nodes)
--   project_work_item_dependencies    -- work item dependencies (graph edges)
--   project_risks                     -- project-level risks
--   project_artifacts                 -- project-level artifact references
--   project_graph_snapshots           -- per-build graph snapshot + validation
--
-- All UUID primary keys use uuid_generate_v4() (uuid-ossp, created in
-- migration 001). PostgreSQL 16 compatible.

BEGIN;

-- ---------------------------------------------------------------------
-- 1. projects -- parent project per user request.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS projects (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_task_id  UUID,
    title           TEXT NOT NULL,
    summary         TEXT,
    request_source  TEXT,
    requester       TEXT,
    project_type    TEXT,
    status          TEXT NOT NULL DEFAULT 'draft',
    autonomy_level  TEXT NOT NULL DEFAULT 'autonomous_dev_test',
    risk_level      TEXT NOT NULL DEFAULT 'low',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_projects_status CHECK (status IN (
        'draft', 'planning', 'planned', 'in_progress', 'blocked',
        'qa', 'delivery_ready', 'accepted', 'cancelled', 'failed'
    )),
    CONSTRAINT chk_projects_autonomy_level CHECK (autonomy_level IN (
        'advisory', 'assisted', 'autonomous_dev_test', 'production_gated'
    )),
    CONSTRAINT chk_projects_risk_level CHECK (risk_level IN (
        'low', 'medium', 'high', 'production'
    ))
);

CREATE INDEX IF NOT EXISTS idx_projects_status ON projects (status);
CREATE INDEX IF NOT EXISTS idx_projects_source_task_id ON projects (source_task_id);

-- ---------------------------------------------------------------------
-- 2. project_briefs.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS project_briefs (
    id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id         UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    version            INTEGER NOT NULL DEFAULT 1,
    problem_statement  TEXT,
    goal               TEXT,
    scope              JSONB NOT NULL DEFAULT '[]'::jsonb,
    non_scope          JSONB NOT NULL DEFAULT '[]'::jsonb,
    assumptions        JSONB NOT NULL DEFAULT '[]'::jsonb,
    constraints        JSONB NOT NULL DEFAULT '[]'::jsonb,
    stakeholders       JSONB NOT NULL DEFAULT '[]'::jsonb,
    success_metrics    JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_by_agent   TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata           JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_project_briefs_project_id ON project_briefs (project_id);

-- ---------------------------------------------------------------------
-- 3. project_user_stories.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS project_user_stories (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    story_key   TEXT,
    actor       TEXT,
    need        TEXT,
    benefit     TEXT,
    priority    TEXT,
    status      TEXT NOT NULL DEFAULT 'draft',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata    JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_project_user_stories_project_id
    ON project_user_stories (project_id);

-- ---------------------------------------------------------------------
-- 4. project_milestones (created before work_items / acceptance_criteria
--    because work_items references it).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS project_milestones (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id    UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    milestone_key TEXT,
    title         TEXT,
    description   TEXT,
    order_index   INTEGER NOT NULL DEFAULT 0,
    status        TEXT NOT NULL DEFAULT 'pending',
    due_at        TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata      JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_project_milestones_status CHECK (status IN (
        'pending', 'in_progress', 'completed', 'blocked', 'cancelled'
    ))
);

CREATE INDEX IF NOT EXISTS idx_project_milestones_project_id
    ON project_milestones (project_id);

-- ---------------------------------------------------------------------
-- 5. project_work_items -- graph nodes.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS project_work_items (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id           UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    milestone_id         UUID REFERENCES project_milestones(id) ON DELETE SET NULL,
    parent_work_item_id  UUID REFERENCES project_work_items(id) ON DELETE SET NULL,
    work_item_key        TEXT,
    title                TEXT NOT NULL,
    description          TEXT,
    work_type            TEXT,
    assigned_agent_role  TEXT,
    status               TEXT NOT NULL DEFAULT 'pending',
    priority             TEXT NOT NULL DEFAULT 'medium',
    estimated_effort     TEXT,
    risk_level           TEXT NOT NULL DEFAULT 'low',
    dispatch_policy      TEXT NOT NULL DEFAULT 'planning_only',
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at         TIMESTAMPTZ,
    metadata             JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_project_work_items_work_type CHECK (work_type IS NULL OR work_type IN (
        'requirement', 'architecture', 'backend', 'frontend', 'database',
        'integration', 'qa', 'security', 'devops', 'documentation', 'release'
    )),
    CONSTRAINT chk_project_work_items_status CHECK (status IN (
        'pending', 'ready', 'in_progress', 'blocked', 'review',
        'completed', 'failed', 'cancelled'
    )),
    CONSTRAINT chk_project_work_items_priority CHECK (priority IN (
        'low', 'medium', 'high', 'critical'
    )),
    CONSTRAINT chk_project_work_items_risk_level CHECK (risk_level IN (
        'low', 'medium', 'high', 'production'
    )),
    CONSTRAINT chk_project_work_items_dispatch_policy CHECK (dispatch_policy IN (
        'planning_only', 'auto_dev_test_allowed', 'approval_required'
    ))
);

CREATE INDEX IF NOT EXISTS idx_project_work_items_project_status
    ON project_work_items (project_id, status);
CREATE INDEX IF NOT EXISTS idx_project_work_items_project_role
    ON project_work_items (project_id, assigned_agent_role);

-- ---------------------------------------------------------------------
-- 6. project_work_item_dependencies -- graph edges.
--    No self-dependency, no duplicate (work_item, depends_on) pair.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS project_work_item_dependencies (
    id                        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id                UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    work_item_id              UUID NOT NULL REFERENCES project_work_items(id) ON DELETE CASCADE,
    depends_on_work_item_id   UUID NOT NULL REFERENCES project_work_items(id) ON DELETE CASCADE,
    dependency_type           TEXT NOT NULL DEFAULT 'blocks',
    created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata                  JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_project_dep_type CHECK (dependency_type IN (
        'blocks', 'informs', 'requires_output', 'review_after'
    )),
    CONSTRAINT chk_project_dep_no_self CHECK (work_item_id <> depends_on_work_item_id),
    CONSTRAINT uq_project_dep_pair UNIQUE (work_item_id, depends_on_work_item_id)
);

CREATE INDEX IF NOT EXISTS idx_project_dep_project_work_item
    ON project_work_item_dependencies (project_id, work_item_id);

-- ---------------------------------------------------------------------
-- 7. project_acceptance_criteria.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS project_acceptance_criteria (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id           UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    work_item_id         UUID REFERENCES project_work_items(id) ON DELETE SET NULL,
    criterion_key        TEXT,
    description          TEXT,
    verification_method  TEXT,
    status               TEXT NOT NULL DEFAULT 'pending',
    required             BOOLEAN NOT NULL DEFAULT true,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata             JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_project_ac_method CHECK (verification_method IS NULL OR verification_method IN (
        'unit_test', 'integration_test', 'e2e_test',
        'manual_review', 'static_check', 'documentation_review'
    )),
    CONSTRAINT chk_project_ac_status CHECK (status IN (
        'pending', 'satisfied', 'failed', 'waived'
    ))
);

CREATE INDEX IF NOT EXISTS idx_project_ac_project_work_item
    ON project_acceptance_criteria (project_id, work_item_id);

-- ---------------------------------------------------------------------
-- 8. project_risks.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS project_risks (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id       UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    risk_key         TEXT,
    title            TEXT,
    description      TEXT,
    severity         TEXT NOT NULL DEFAULT 'low',
    likelihood       TEXT NOT NULL DEFAULT 'low',
    mitigation       TEXT,
    owner_agent_role TEXT,
    status           TEXT NOT NULL DEFAULT 'open',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata         JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_project_risks_severity CHECK (severity IN (
        'low', 'medium', 'high', 'critical'
    )),
    CONSTRAINT chk_project_risks_likelihood CHECK (likelihood IN (
        'low', 'medium', 'high'
    )),
    CONSTRAINT chk_project_risks_status CHECK (status IN (
        'open', 'mitigated', 'accepted', 'closed'
    ))
);

CREATE INDEX IF NOT EXISTS idx_project_risks_project_id ON project_risks (project_id);

-- ---------------------------------------------------------------------
-- 9. project_artifacts.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS project_artifacts (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id       UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    work_item_id     UUID REFERENCES project_work_items(id) ON DELETE SET NULL,
    artifact_type    TEXT,
    title            TEXT,
    content          JSONB,
    uri              TEXT,
    created_by_agent TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata         JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_project_artifacts_project_id ON project_artifacts (project_id);

-- ---------------------------------------------------------------------
-- 10. project_graph_snapshots -- one row per graph build / rebuild.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS project_graph_snapshots (
    id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id         UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    version            INTEGER NOT NULL DEFAULT 1,
    graph_hash         TEXT,
    nodes              JSONB NOT NULL DEFAULT '[]'::jsonb,
    edges              JSONB NOT NULL DEFAULT '[]'::jsonb,
    validation_status  TEXT NOT NULL DEFAULT 'valid',
    validation_errors  JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_by_agent   TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata           JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_project_graph_validation_status CHECK (validation_status IN (
        'valid', 'invalid', 'warning'
    ))
);

CREATE INDEX IF NOT EXISTS idx_project_graph_snapshots_project_version
    ON project_graph_snapshots (project_id, version);

COMMIT;
