-- Step 57 (Stage 59A) -- Multi-project Delivery Capability & Work-item Dispatch.
--
-- Extends the existing project-planner schema (017) with a delivery + dispatch
-- layer: project registry semantics, a work-item delivery lifecycle, work-item
-- dispatch records + events, project delivery-state rollup, and delivery-package
-- linkage. Idempotent (ADD COLUMN / CREATE TABLE IF NOT EXISTS). UUID PKs, FKs,
-- indexes. NO production-execution default true; production_effect defaults false.
--
-- This does NOT recreate the existing `projects` / `project_work_items` /
-- `project_work_item_dependencies` tables (017); it extends them.

-- ---- projects: registry semantics --------------------------------------------
ALTER TABLE projects ADD COLUMN IF NOT EXISTS project_key TEXT;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS environment_scope TEXT NOT NULL DEFAULT 'dev';
ALTER TABLE projects ADD COLUMN IF NOT EXISTS production_allowed BOOLEAN NOT NULL DEFAULT false;
-- Step 57 registry lifecycle (separate from the planner `status`; active by default).
ALTER TABLE projects ADD COLUMN IF NOT EXISTS registry_status TEXT NOT NULL DEFAULT 'active';
CREATE UNIQUE INDEX IF NOT EXISTS uq_projects_project_key
    ON projects (project_key) WHERE project_key IS NOT NULL;

-- ---- project_work_items: delivery + dispatch attributes -----------------------
ALTER TABLE project_work_items ADD COLUMN IF NOT EXISTS item_source TEXT;
ALTER TABLE project_work_items ADD COLUMN IF NOT EXISTS requested_by TEXT;
ALTER TABLE project_work_items ADD COLUMN IF NOT EXISTS assigned_agent TEXT;
ALTER TABLE project_work_items ADD COLUMN IF NOT EXISTS requires_human_approval BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE project_work_items ADD COLUMN IF NOT EXISTS production_effect BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE project_work_items ADD COLUMN IF NOT EXISTS delivery_package_id UUID;
-- Step 57 delivery lifecycle state (separate from the planner `status`; enforced
-- by shared/sdk/work_items/lifecycle.py against work-item-lifecycle.yaml).
ALTER TABLE project_work_items ADD COLUMN IF NOT EXISTS lifecycle_state TEXT NOT NULL DEFAULT 'created';

-- ---- project_members ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS project_members (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    member_key  TEXT NOT NULL,
    role        TEXT NOT NULL DEFAULT 'member',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_project_members UNIQUE (project_id, member_key)
);
CREATE INDEX IF NOT EXISTS idx_project_members_project_id ON project_members (project_id);

-- ---- work_item_dispatches ----------------------------------------------------
CREATE TABLE IF NOT EXISTS work_item_dispatches (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    work_item_id    UUID NOT NULL REFERENCES project_work_items(id) ON DELETE CASCADE,
    dispatch_key    TEXT NOT NULL,
    target_agent    TEXT NOT NULL,
    target_stream   TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    attempt         INTEGER NOT NULL DEFAULT 1,
    correlation_id  TEXT,
    production_effect BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ,
    failure_reason  TEXT,
    CONSTRAINT chk_work_item_dispatches_status CHECK (status IN (
        'pending', 'dispatched', 'in_progress', 'completed', 'failed', 'cancelled'
    ))
);
CREATE INDEX IF NOT EXISTS idx_wid_project_id ON work_item_dispatches (project_id);
CREATE INDEX IF NOT EXISTS idx_wid_status ON work_item_dispatches (status);
CREATE INDEX IF NOT EXISTS idx_wid_correlation_id ON work_item_dispatches (correlation_id);
CREATE INDEX IF NOT EXISTS idx_wid_work_item_id ON work_item_dispatches (work_item_id);

-- ---- work_item_events --------------------------------------------------------
CREATE TABLE IF NOT EXISTS work_item_events (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    work_item_id    UUID NOT NULL REFERENCES project_work_items(id) ON DELETE CASCADE,
    event_type      TEXT NOT NULL,
    from_state      TEXT,
    to_state        TEXT,
    actor           TEXT,
    role            TEXT,
    reason          TEXT,
    correlation_id  TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_wie_project_id ON work_item_events (project_id);
CREATE INDEX IF NOT EXISTS idx_wie_work_item_id ON work_item_events (work_item_id);
CREATE INDEX IF NOT EXISTS idx_wie_correlation_id ON work_item_events (correlation_id);

-- ---- project_delivery_states (rollup) ----------------------------------------
CREATE TABLE IF NOT EXISTS project_delivery_states (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id       UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    delivery_state   TEXT NOT NULL DEFAULT 'not_started',
    production_ready  BOOLEAN NOT NULL DEFAULT false,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata         JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT uq_project_delivery_states UNIQUE (project_id),
    CONSTRAINT chk_project_delivery_state CHECK (delivery_state IN (
        'not_started', 'intake_active', 'planning_active', 'implementation_active',
        'qa_active', 'packaging_active', 'operator_review', 'completed_nonproduction',
        'blocked', 'cancelled'
    ))
);
CREATE INDEX IF NOT EXISTS idx_pds_project_id ON project_delivery_states (project_id);

-- ---- project_delivery_packages (linkage) -------------------------------------
CREATE TABLE IF NOT EXISTS project_delivery_packages (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id           UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    work_item_id         UUID REFERENCES project_work_items(id) ON DELETE SET NULL,
    dispatch_id          UUID REFERENCES work_item_dispatches(id) ON DELETE SET NULL,
    delivery_package_id  UUID,
    acceptance_status    TEXT NOT NULL DEFAULT 'pending',
    production_ready      BOOLEAN NOT NULL DEFAULT false,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata             JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_pdp_acceptance_status CHECK (acceptance_status IN (
        'pending', 'operator_review', 'accepted_nonproduction', 'rejected'
    ))
);
CREATE INDEX IF NOT EXISTS idx_pdp_project_id ON project_delivery_packages (project_id);
CREATE INDEX IF NOT EXISTS idx_pdp_work_item_id ON project_delivery_packages (work_item_id);
