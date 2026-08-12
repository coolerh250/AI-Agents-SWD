-- 036_delivery_acceptance_persistence.sql
-- Step 66D-BE1 -- Delivery Acceptance persistence foundation.
--
-- STRICTLY ADDITIVE + IDEMPOTENT. Creates the five canonical acceptance-domain tables and touches
-- NOTHING that already exists: no column is added to an existing table, no existing constraint is
-- altered, no row is rewritten, no backfill is performed. The legacy Step 47/49 `delivery_packages`
-- family (migration 021) is untouched and is referenced ONLY additively, by id, from
-- delivery_submissions.legacy_delivery_package_refs (66D-D04 / D04-R5).
--
--   delivery_submissions        the human-acceptance aggregate (66D-D04)
--   delivery_review_tasks       the human-review anchor (66D-D03), structural active state (66D-D05)
--   delivery_review_actions     append-only recorded Review Gate Actions (66D-D01)
--   product_owner_decisions     append-only, supersedable final decisions (66D-D02)
--   acceptance_follow_up_items  follow-ups raised by a decision
--
-- SCHEMA ONLY. This migration wires up NO HTTP endpoint, NO router, NO event producer, NO outbox
-- row, NO relay, NO projector, NO read model, NO scheduler and NO identity/RBAC change. TASK_ROLES
-- is referenced (as a CHECK allowlist on delivery_review_tasks.assigned_roles) and NOT modified.
-- No secret, credential, DSN, raw token or private chain of thought is stored by any column here.
-- `production_executed_true_count` stays 0: nothing in this migration can execute anything.
--
-- 66D-D05 (BINDING) governs delivery_review_tasks:
--     active := closed_at IS NULL          closed := closed_at IS NOT NULL
--   There is deliberately NO status / review_status / lifecycle-enum column on that table, and
--   DeliverySubmission.status is never mirrored into it. The single persistence invariant is
--   AT MOST ONE active task per delivery_submission_id, enforced by a PARTIAL unique index. There
--   is no trigger forcing one to exist: zero active tasks is a legal state (D05-R6).
--
-- PostgreSQL 16. UUID PKs via uuid_generate_v4() (uuid-ossp, migration 001). DB-authoritative time
-- via statement_timestamp() everywhere (66C.4 convention) -- never a client clock. A matching
-- 036_delivery_acceptance_persistence_down.sql reverses it.

BEGIN;

-- ---------------------------------------------------------------------------------------------
-- 1. delivery_submissions -- the human-acceptance aggregate.
--
--    Execution lineage (project -> work item -> workflow -> run) is the 66D-D03 anchor. project_id
--    and primary_work_item_id have real FKs to the canonical owning tables (projects,
--    project_work_items, migration 017). workflow_id / run_id are recorded WITHOUT a FK because
--    this repository has no single canonical UUID-PK workflow/run entity to point at
--    (workflow_states.task_id is TEXT since migration 003, and agent_executions is keyed the same
--    way) -- the same documented reason production_action_approvals.resource_id carries no FK.
--    They are "workflow/run lineage where defined" and stay nullable until such an entity exists.
--
--    ON DELETE RESTRICT everywhere: acceptance history must never be silently cascade-deleted when
--    a parent record is removed. Decisions outlive submissions (ARCH1 section 1, Retention).
-- ---------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS delivery_submissions (
    delivery_submission_id       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Execution lineage (66D-D03 / D03-R1).
    project_id                   UUID NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    primary_work_item_id         UUID NOT NULL
                                     REFERENCES project_work_items(id) ON DELETE RESTRICT,
    workflow_id                  UUID,
    run_id                       UUID,

    -- Versioning (ARCH1 rules 6 and 7; 66D-D05 / D05-R5). A re-submission is a NEW row that
    -- supersedes its predecessor; an existing submission is never rewritten in place. Version 1 is
    -- the chain root. See chk_ds_root_is_version_one and uq_ds_supersedes below: together they make
    -- the chain strictly linear, which is what makes delivery_submission_id the version boundary.
    submission_version           INTEGER NOT NULL DEFAULT 1,
    supersedes_submission_id     UUID
                                     REFERENCES delivery_submissions(delivery_submission_id)
                                     ON DELETE RESTRICT,

    -- The nine canonical statuses, and only those (66D-D02).
    status                       TEXT NOT NULL DEFAULT 'DRAFT',

    -- Baseline and linkage.
    requirements_baseline_id     TEXT,
    acceptance_criteria_version  TEXT,
    -- Additive, reference-only pointer at the legacy Step 47/49 evidence packages (66D-D04 /
    -- D04-R5). The legacy rows are never modified, repurposed or backfilled.
    legacy_delivery_package_refs UUID[] NOT NULL DEFAULT '{}'::uuid[],

    -- Lifecycle. Every timestamp is DB-authoritative; review_due_at drives EXPIRED (ARCH1 rule 9).
    created_by_actor             TEXT NOT NULL,
    submitted_at                 TIMESTAMPTZ,
    submitted_by_actor           TEXT,
    review_due_at                TIMESTAMPTZ,

    -- Evidence / reference linkage. Identifiers and refs only -- never raw tokens, secrets,
    -- credentials, DSNs or private chain of thought.
    evidence_refs                JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Optimistic concurrency (ARCH1 rule 10). Every repository mutation is a CAS on this column.
    row_version                  INTEGER NOT NULL DEFAULT 1,

    created_at                   TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
    updated_at                   TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),

    CONSTRAINT chk_ds_status CHECK (status IN (
        'DRAFT', 'SUBMITTED', 'UNDER_REVIEW', 'CHANGES_REQUESTED', 'QA_RERUN_REQUESTED',
        'ACCEPTED', 'REJECTED', 'ARCHIVED', 'EXPIRED'
    )),
    CONSTRAINT chk_ds_version_positive CHECK (submission_version >= 1),
    -- A submission with no predecessor is version 1; any later version must name its predecessor.
    CONSTRAINT chk_ds_root_is_version_one CHECK (
        (supersedes_submission_id IS NULL) = (submission_version = 1)
    ),
    CONSTRAINT chk_ds_no_self_supersession CHECK (
        supersedes_submission_id IS NULL OR supersedes_submission_id <> delivery_submission_id
    ),
    CONSTRAINT chk_ds_row_version_positive CHECK (row_version >= 1),
    CONSTRAINT chk_ds_submitted_coherent CHECK (
        (submitted_at IS NULL) = (submitted_by_actor IS NULL)
    ),
    CONSTRAINT chk_ds_created_by_bounded CHECK (length(btrim(created_by_actor)) BETWEEN 1 AND 128),
    CONSTRAINT chk_ds_submitted_by_bounded CHECK (
        submitted_by_actor IS NULL OR length(submitted_by_actor) <= 128
    )
);

-- Submission-version uniqueness. A given version may be superseded by AT MOST ONE successor, so a
-- version chain can never fork and can never contain two rows claiming the same position. Combined
-- with chk_ds_root_is_version_one and the repository deriving version = predecessor + 1 (never
-- caller-supplied), this is the authoritative DB protection for the canonical version model.
CREATE UNIQUE INDEX IF NOT EXISTS uq_ds_supersedes
    ON delivery_submissions (supersedes_submission_id)
    WHERE supersedes_submission_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_ds_project_status
    ON delivery_submissions (project_id, status);
CREATE INDEX IF NOT EXISTS idx_ds_work_item
    ON delivery_submissions (primary_work_item_id);
CREATE INDEX IF NOT EXISTS idx_ds_review_due_at
    ON delivery_submissions (review_due_at)
    WHERE review_due_at IS NOT NULL;

-- ---------------------------------------------------------------------------------------------
-- 2. delivery_review_tasks -- the human-review anchor (66D-D03), structural active state (66D-D05).
--
--    THERE IS NO status / review_status / lifecycle-enum COLUMN HERE, DELIBERATELY.
--    66D-D05 (D05-R1, D05-R2, D05-R3, D05-R8) makes active state structural:
--        active := closed_at IS NULL      closed := closed_at IS NOT NULL
--    closed_at is a STRUCTURAL marker only. It never implies ACCEPTED, REJECTED, EXPIRED,
--    ARCHIVED, a recorded ProductOwnerDecision, completed QA, or a terminal submission status
--    (D05-R7). The authoritative acceptance record is product_owner_decisions.
--
--    The review task carries no copy of the submission's status: submission state and review-task
--    structural state are independent, which is exactly what lets a closed review task coexist with
--    an EXPIRED submission (DESIGN delivery-inbox-spec section 3, preserved by 66D-D05).
-- ---------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS delivery_review_tasks (
    delivery_review_task_id  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    delivery_submission_id   UUID NOT NULL
                                 REFERENCES delivery_submissions(delivery_submission_id)
                                 ON DELETE RESTRICT,
    -- The existing operator task this review hangs off -- the TASK_ROLES/RBAC anchor (66D-D03).
    -- operator_tasks (migration 029) is unchanged by this migration.
    task_id                  UUID NOT NULL REFERENCES operator_tasks(id) ON DELETE RESTRICT,

    -- Assignment. Roles are constrained to the canonical TASK_ROLES set (shared/sdk/tasks/rbac.py);
    -- this migration REFERENCES that set as an allowlist and does not modify RBAC.
    assigned_roles           TEXT[] NOT NULL DEFAULT '{}'::text[],
    assigned_actor_refs      TEXT[] NOT NULL DEFAULT '{}'::text[],

    review_due_at            TIMESTAMPTZ,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
    -- ACTIVE-STATE AUTHORITY (66D-D05). NULL => active. NOT NULL => closed. Nothing else.
    closed_at                TIMESTAMPTZ,

    row_version              INTEGER NOT NULL DEFAULT 1,

    CONSTRAINT chk_drt_row_version_positive CHECK (row_version >= 1),
    CONSTRAINT chk_drt_assigned_roles CHECK (
        assigned_roles <@ ARRAY[
            'requester', 'pm_engineering_lead', 'reviewer_approver',
            'platform_admin', 'agent_operator', 'security_compliance_reviewer'
        ]::text[]
    ),
    CONSTRAINT chk_drt_closed_after_created CHECK (closed_at IS NULL OR closed_at >= created_at)
);

-- THE 66D-D05 PERSISTENCE INVARIANT (D05-R4).
--   AT MOST ONE structurally active DeliveryReviewTask per delivery_submission_id.
-- PARTIAL, not plain: closed tasks are excluded, so any number of closed tasks may coexist with
-- one active task for the same submission. There is deliberately NO trigger or constraint forcing
-- an active task to EXIST -- required existence is DEFERRED (D05-R6).
CREATE UNIQUE INDEX IF NOT EXISTS uq_drt_active_per_submission
    ON delivery_review_tasks (delivery_submission_id)
    WHERE closed_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_drt_submission
    ON delivery_review_tasks (delivery_submission_id);
CREATE INDEX IF NOT EXISTS idx_drt_task
    ON delivery_review_tasks (task_id);
CREATE INDEX IF NOT EXISTS idx_drt_open_due
    ON delivery_review_tasks (review_due_at)
    WHERE closed_at IS NULL;

-- ---------------------------------------------------------------------------------------------
-- 3. delivery_review_actions -- append-only Review Gate Actions (66D-D01, exactly six).
--
--    Structurally append-only: the table has NO updated_at and NO row_version, so there is nothing
--    an update could legitimately advance, and the acceptance-domain repository exposes no update
--    or delete operation for it. A correction is a NEW action, never an edit (ARCH1 section 3).
-- ---------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS delivery_review_actions (
    review_action_id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    delivery_submission_id   UUID NOT NULL
                                 REFERENCES delivery_submissions(delivery_submission_id)
                                 ON DELETE RESTRICT,
    delivery_review_task_id  UUID NOT NULL
                                 REFERENCES delivery_review_tasks(delivery_review_task_id)
                                 ON DELETE RESTRICT,

    action_type              TEXT NOT NULL,
    -- Actor reference only. NOT a verified identity: request-supplied actor/role fields are never
    -- authoritative, and verified human identity is RA-2 work (ARCH1-G08), not implemented.
    actor_ref                TEXT NOT NULL,
    actor_role               TEXT,

    reason                   TEXT,
    requested_scope          TEXT,
    previous_qa_ref          TEXT,

    idempotency_key          TEXT NOT NULL,
    audit_event_id           UUID,

    created_at               TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),

    -- The six Review Gate Actions, and only those. ACCEPTED_WITH_FOLLOW_UP is a Product Owner
    -- Final Decision and must never appear here (D01-R9).
    CONSTRAINT chk_dra_action_type CHECK (action_type IN (
        'ACCEPT', 'REJECT', 'REQUEST_CHANGES', 'RERUN_QA', 'ESCALATE', 'ARCHIVE'
    )),
    -- ARCH1 section 3: reason is required for REQUEST_CHANGES, RERUN_QA, ESCALATE and REJECT.
    CONSTRAINT chk_dra_reason_required CHECK (
        action_type NOT IN ('REQUEST_CHANGES', 'RERUN_QA', 'ESCALATE', 'REJECT')
        OR (reason IS NOT NULL AND length(btrim(reason)) > 0)
    ),
    -- ARCH1 section 3: RERUN_QA must say what is re-verified and what is being re-verified.
    CONSTRAINT chk_dra_rerun_qa_scope CHECK (
        action_type <> 'RERUN_QA'
        OR (requested_scope IS NOT NULL AND length(btrim(requested_scope)) > 0
            AND previous_qa_ref IS NOT NULL AND length(btrim(previous_qa_ref)) > 0)
    ),
    CONSTRAINT chk_dra_actor_bounded CHECK (length(btrim(actor_ref)) BETWEEN 1 AND 128),
    CONSTRAINT chk_dra_idempotency_key_bounded CHECK (
        length(btrim(idempotency_key)) BETWEEN 1 AND 256
    )
);

-- Durable duplicate prevention (ARCH1 section 3: "unique per (submission, actor, logical intent)").
-- The uniqueness boundary is the submission, exactly as the canonical contract scopes it. BE1 is
-- responsible for durable duplicate PREVENTION only -- HTTP retry replay, middleware and request
-- dedupe controllers are NOT in this stage.
CREATE UNIQUE INDEX IF NOT EXISTS uq_dra_submission_idempotency_key
    ON delivery_review_actions (delivery_submission_id, idempotency_key);

CREATE INDEX IF NOT EXISTS idx_dra_submission_created
    ON delivery_review_actions (delivery_submission_id, created_at);
CREATE INDEX IF NOT EXISTS idx_dra_review_task
    ON delivery_review_actions (delivery_review_task_id);
CREATE INDEX IF NOT EXISTS idx_dra_submission_action_type
    ON delivery_review_actions (delivery_submission_id, action_type);

-- ---------------------------------------------------------------------------------------------
-- 4. product_owner_decisions -- append-only, supersedable, THE authoritative acceptance record
--    (66D-D02). Never updated in place, never deleted. A correction is a NEW row whose
--    supersedes_decision_id names the row it replaces; the superseded row stays queryable forever.
--
--    Structurally append-only, same as review actions: no updated_at, no row_version, and the
--    repository exposes no update or delete operation.
-- ---------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS product_owner_decisions (
    decision_id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    delivery_submission_id   UUID NOT NULL
                                 REFERENCES delivery_submissions(delivery_submission_id)
                                 ON DELETE RESTRICT,
    delivery_review_task_id  UUID
                                 REFERENCES delivery_review_tasks(delivery_review_task_id)
                                 ON DELETE RESTRICT,

    -- The three Product Owner Final Decisions, and only those. No Review Gate Action value may
    -- ever be added here (D01-R8).
    decision_type            TEXT NOT NULL,
    decision_reason          TEXT NOT NULL,
    decided_by_actor         TEXT NOT NULL,
    decided_at               TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),

    evidence_reviewed        JSONB NOT NULL DEFAULT '[]'::jsonb,

    supersedes_decision_id   UUID
                                 REFERENCES product_owner_decisions(decision_id)
                                 ON DELETE RESTRICT,
    decision_version         INTEGER NOT NULL DEFAULT 1,

    idempotency_key          TEXT NOT NULL,
    audit_event_id           UUID,

    created_at               TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),

    CONSTRAINT chk_pod_decision_type CHECK (decision_type IN (
        'ACCEPTED', 'ACCEPTED_WITH_FOLLOW_UP', 'REJECTED'
    )),
    CONSTRAINT chk_pod_reason_nonempty CHECK (length(btrim(decision_reason)) > 0),
    CONSTRAINT chk_pod_decided_by_bounded CHECK (
        length(btrim(decided_by_actor)) BETWEEN 1 AND 128
    ),
    CONSTRAINT chk_pod_version_positive CHECK (decision_version >= 1),
    -- The first decision for a submission has no predecessor; every later one names the decision
    -- it supersedes. With uq_pod_supersedes below, the supersession chain is strictly linear, so a
    -- cycle is structurally impossible (it would require a row preceding itself).
    CONSTRAINT chk_pod_root_is_version_one CHECK (
        (supersedes_decision_id IS NULL) = (decision_version = 1)
    ),
    CONSTRAINT chk_pod_no_self_supersession CHECK (
        supersedes_decision_id IS NULL OR supersedes_decision_id <> decision_id
    ),
    CONSTRAINT chk_pod_idempotency_key_bounded CHECK (
        length(btrim(idempotency_key)) BETWEEN 1 AND 256
    )
);

-- decision_version is monotonic per submission (ARCH1 section 4).
CREATE UNIQUE INDEX IF NOT EXISTS uq_pod_submission_version
    ON product_owner_decisions (delivery_submission_id, decision_version);

-- A decision may be superseded by AT MOST ONE successor: no forked history, no diamond.
CREATE UNIQUE INDEX IF NOT EXISTS uq_pod_supersedes
    ON product_owner_decisions (supersedes_decision_id)
    WHERE supersedes_decision_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_pod_submission_idempotency_key
    ON product_owner_decisions (delivery_submission_id, idempotency_key);

CREATE INDEX IF NOT EXISTS idx_pod_submission_decided_at
    ON product_owner_decisions (delivery_submission_id, decided_at);
CREATE INDEX IF NOT EXISTS idx_pod_review_task
    ON product_owner_decisions (delivery_review_task_id)
    WHERE delivery_review_task_id IS NOT NULL;

-- ---------------------------------------------------------------------------------------------
-- 5. acceptance_follow_up_items -- follow-ups raised BY a decision (ARCH1 section 5).
--
--    OPEN / IN_PROGRESS / CLOSED / CANCELLED is THIS entity's lifecycle and only this one. It must
--    never be reused as a DeliveryReviewTask lifecycle (66D-D05 / D05-R8).
--
--    NOTE the deliberate omission: there is NO constraint or trigger tying `blocking` to the
--    parent decision_type. "ACCEPTED_WITH_FOLLOW_UP accepts only blocking = false" is Step 66D-BE3
--    action/transaction policy (409 BLOCKING_FOLLOW_UP_REQUIRES_CHANGES). BE1 provides the
--    persistence primitives for it and must not implement it early.
-- ---------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS acceptance_follow_up_items (
    follow_up_item_id  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    -- A follow-up belongs to a DECISION, not to a submission (ARCH1 section 5).
    decision_id        UUID NOT NULL
                           REFERENCES product_owner_decisions(decision_id) ON DELETE RESTRICT,

    description        TEXT NOT NULL,
    owner_actor_ref    TEXT NOT NULL,
    severity           TEXT NOT NULL,
    blocking           BOOLEAN NOT NULL DEFAULT false,
    due_at             TIMESTAMPTZ,

    status             TEXT NOT NULL DEFAULT 'OPEN',

    evidence_refs      JSONB NOT NULL DEFAULT '[]'::jsonb,

    created_at         TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
    closed_at          TIMESTAMPTZ,

    row_version        INTEGER NOT NULL DEFAULT 1,

    CONSTRAINT chk_afi_status CHECK (status IN ('OPEN', 'IN_PROGRESS', 'CLOSED', 'CANCELLED')),
    CONSTRAINT chk_afi_description_nonempty CHECK (length(btrim(description)) > 0),
    CONSTRAINT chk_afi_owner_bounded CHECK (length(btrim(owner_actor_ref)) BETWEEN 1 AND 128),
    CONSTRAINT chk_afi_severity_bounded CHECK (length(btrim(severity)) BETWEEN 1 AND 64),
    CONSTRAINT chk_afi_row_version_positive CHECK (row_version >= 1)
);

CREATE INDEX IF NOT EXISTS idx_afi_decision
    ON acceptance_follow_up_items (decision_id);
CREATE INDEX IF NOT EXISTS idx_afi_open_blocking
    ON acceptance_follow_up_items (decision_id, blocking)
    WHERE status IN ('OPEN', 'IN_PROGRESS');

COMMIT;
