"""Step 66D-BE1 -- delivery acceptance repository.

Transaction-aware asyncpg repository over the five acceptance tables (migration 036). Follows the
established repository convention in this repository exactly: module-level async functions that
take the CALLER's connection and run inside the caller's transaction (never a connection per
call), guarded `UPDATE ... RETURNING` for CAS, and PostgreSQL `statement_timestamp()` as the only
authoritative clock -- never a Python or client clock.

Scope boundaries this module deliberately does NOT cross:

  * No HTTP route, router, controller, middleware or request dedupe. Idempotency here is DURABLE
    DUPLICATE PREVENTION only; retry-response replay is not BE1's job.
  * No event, outbox row, relay, consumer or projector (Step 66D-BE4).
  * No review-task transition semantics -- no automatic close, no reopen, no close-on-accept,
    close-on-reject or close-on-expiry. 66D-D05 section 7 defers all of them. `close_review_task`
    is a bare CAS primitive an authorized later stage can call; it decides nothing itself.
  * No `ACCEPTED_WITH_FOLLOW_UP` + blocking-follow-up validation (Step 66D-BE3 policy).
  * No status projection write: `projected_submission_status` exists in the model as a pure
    helper, and nothing here applies it.

Append-only boundary (ARCH1 sections 3 and 4): this module exposes NO update and NO delete
operation for `delivery_review_actions` or `product_owner_decisions`. Those two tables also carry
no `updated_at` and no `row_version`, so there is no column an update could legitimately advance.
A correction is a new action, or a new decision with `supersedes_decision_id` set.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import asyncpg

from shared.sdk.delivery_acceptance import acceptance_model as model


def _row(record: asyncpg.Record | None) -> dict[str, Any] | None:
    return dict(record) if record is not None else None


async def db_now(conn: asyncpg.Connection) -> datetime:
    """The authoritative clock for this domain: PostgreSQL, never the caller's machine."""
    return await conn.fetchval("SELECT statement_timestamp()")


# ---- DeliverySubmission -------------------------------------------------------------------------


async def create_submission(
    conn: asyncpg.Connection,
    *,
    project_id: str,
    primary_work_item_id: str,
    created_by_actor: str,
    workflow_id: str | None = None,
    run_id: str | None = None,
    status: str = "DRAFT",
    requirements_baseline_id: str | None = None,
    acceptance_criteria_version: str | None = None,
    legacy_delivery_package_refs: list[str] | None = None,
    review_due_at: datetime | None = None,
    evidence_refs: str = "{}",
) -> dict[str, Any]:
    """Create a version-1 DeliverySubmission (the root of a version chain).

    `legacy_delivery_package_refs` is an ADDITIVE reference at the legacy Step 47/49 packages
    (66D-D04 / D04-R5). Nothing in this module reads, rewrites or backfills a legacy row.
    """
    model.assert_submission_status(status)
    record = await conn.fetchrow(
        """
        INSERT INTO delivery_submissions
          (project_id, primary_work_item_id, workflow_id, run_id, status,
           requirements_baseline_id, acceptance_criteria_version, legacy_delivery_package_refs,
           created_by_actor, review_due_at, evidence_refs)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::jsonb)
        RETURNING *
        """,
        project_id,
        primary_work_item_id,
        workflow_id,
        run_id,
        status,
        requirements_baseline_id,
        acceptance_criteria_version,
        legacy_delivery_package_refs or [],
        created_by_actor,
        review_due_at,
        evidence_refs,
    )
    assert record is not None
    return dict(record)


async def get_submission(
    conn: asyncpg.Connection, delivery_submission_id: str
) -> dict[str, Any] | None:
    return _row(
        await conn.fetchrow(
            "SELECT * FROM delivery_submissions WHERE delivery_submission_id=$1",
            delivery_submission_id,
        )
    )


async def create_next_submission_version(
    conn: asyncpg.Connection,
    *,
    supersedes_submission_id: str,
    created_by_actor: str,
    status: str = "DRAFT",
    evidence_refs: str = "{}",
) -> dict[str, Any]:
    """Create the next version of a submission (ARCH1 rules 6 and 7).

    `submission_version` is DERIVED here from the locked predecessor row, never supplied by the
    caller, so a caller cannot inject a duplicate or non-monotonic version. The predecessor is
    locked FOR UPDATE for the rest of this transaction; a concurrent second attempt to supersede
    the same predecessor is then rejected by `uq_ds_supersedes`.

    Project and work-item lineage are inherited from the predecessor: a new version of the same
    logical submission cannot silently move to a different project or work item.
    """
    model.assert_submission_status(status)
    predecessor = _row(
        await conn.fetchrow(
            "SELECT * FROM delivery_submissions WHERE delivery_submission_id=$1 FOR UPDATE",
            supersedes_submission_id,
        )
    )
    if predecessor is None:
        raise ValueError("supersedes_submission_id does not exist")

    record = await conn.fetchrow(
        """
        INSERT INTO delivery_submissions
          (project_id, primary_work_item_id, workflow_id, run_id, status,
           requirements_baseline_id, acceptance_criteria_version, legacy_delivery_package_refs,
           created_by_actor, review_due_at, evidence_refs,
           submission_version, supersedes_submission_id)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::jsonb,$12,$13)
        RETURNING *
        """,
        predecessor["project_id"],
        predecessor["primary_work_item_id"],
        predecessor["workflow_id"],
        predecessor["run_id"],
        status,
        predecessor["requirements_baseline_id"],
        predecessor["acceptance_criteria_version"],
        predecessor["legacy_delivery_package_refs"],
        created_by_actor,
        predecessor["review_due_at"],
        evidence_refs,
        int(predecessor["submission_version"]) + 1,
        supersedes_submission_id,
    )
    assert record is not None
    return dict(record)


async def cas_update_submission_status(
    conn: asyncpg.Connection,
    delivery_submission_id: str,
    *,
    status: str,
    expected_row_version: int,
    submitted_at: datetime | None = None,
    submitted_by_actor: str | None = None,
) -> dict[str, Any] | None:
    """Optimistic-concurrency status mutation (ARCH1 rule 10).

    Returns the updated row when `expected_row_version` matched, and None when it was stale --
    a deterministic conflict signal. Mapping that to an HTTP 409 is Step 66D-BE2/BE3 work; this
    layer does not know about HTTP.

    `row_version` advances by exactly one per successful mutation, so two racing callers holding
    the same expected version can never both succeed.
    """
    model.assert_submission_status(status)
    return _row(
        await conn.fetchrow(
            """
            UPDATE delivery_submissions
            SET status=$2,
                submitted_at=COALESCE($4, submitted_at),
                submitted_by_actor=COALESCE($5, submitted_by_actor),
                row_version=row_version + 1,
                updated_at=statement_timestamp()
            WHERE delivery_submission_id=$1 AND row_version=$3
            RETURNING *
            """,
            delivery_submission_id,
            status,
            expected_row_version,
            submitted_at,
            submitted_by_actor,
        )
    )


# ---- DeliveryReviewTask (66D-D05) ---------------------------------------------------------------


async def create_review_task(
    conn: asyncpg.Connection,
    *,
    delivery_submission_id: str,
    task_id: str,
    assigned_roles: list[str] | None = None,
    assigned_actor_refs: list[str] | None = None,
    review_due_at: datetime | None = None,
) -> dict[str, Any]:
    """Create a structurally ACTIVE review task (`closed_at` is NULL by construction).

    A second active task for the same `delivery_submission_id` is rejected by the authoritative
    partial unique index `uq_drt_active_per_submission` -- asyncpg raises UniqueViolationError.
    That index, not this function, is the enforcement point (66D-D05 / D05-R4).

    No status is written, because there is no status column: active state is structural.
    """
    roles = model.assert_assigned_roles(list(assigned_roles or []))
    record = await conn.fetchrow(
        """
        INSERT INTO delivery_review_tasks
          (delivery_submission_id, task_id, assigned_roles, assigned_actor_refs, review_due_at)
        VALUES ($1,$2,$3,$4,$5)
        RETURNING *
        """,
        delivery_submission_id,
        task_id,
        roles,
        list(assigned_actor_refs or []),
        review_due_at,
    )
    assert record is not None
    return dict(record)


async def get_review_task(
    conn: asyncpg.Connection, delivery_review_task_id: str
) -> dict[str, Any] | None:
    return _row(
        await conn.fetchrow(
            "SELECT * FROM delivery_review_tasks WHERE delivery_review_task_id=$1",
            delivery_review_task_id,
        )
    )


async def get_active_review_task(
    conn: asyncpg.Connection, delivery_submission_id: str
) -> dict[str, Any] | None:
    """The submission's structurally active review task, if it has one.

    The predicate is `closed_at IS NULL` and nothing else (66D-D05). Returning None is a legal,
    ordinary state: required existence is DEFERRED (D05-R6), so a submission may have zero active
    review tasks and that is not an error.
    """
    return _row(
        await conn.fetchrow(
            """
            SELECT * FROM delivery_review_tasks
            WHERE delivery_submission_id=$1 AND closed_at IS NULL
            """,
            delivery_submission_id,
        )
    )


async def cas_update_review_task_assignment(
    conn: asyncpg.Connection,
    delivery_review_task_id: str,
    *,
    expected_row_version: int,
    assigned_roles: list[str] | None = None,
    assigned_actor_refs: list[str] | None = None,
    review_due_at: datetime | None = None,
) -> dict[str, Any] | None:
    """CAS assignment mutation. Returns None on a stale expected version."""
    roles = (
        model.assert_assigned_roles(list(assigned_roles)) if assigned_roles is not None else None
    )
    return _row(
        await conn.fetchrow(
            """
            UPDATE delivery_review_tasks
            SET assigned_roles=COALESCE($3, assigned_roles),
                assigned_actor_refs=COALESCE($4, assigned_actor_refs),
                review_due_at=COALESCE($5, review_due_at),
                row_version=row_version + 1,
                updated_at=statement_timestamp()
            WHERE delivery_review_task_id=$1 AND row_version=$2
            RETURNING *
            """,
            delivery_review_task_id,
            expected_row_version,
            roles,
            list(assigned_actor_refs) if assigned_actor_refs is not None else None,
            review_due_at,
        )
    )


async def close_review_task(
    conn: asyncpg.Connection,
    delivery_review_task_id: str,
    *,
    expected_row_version: int,
) -> dict[str, Any] | None:
    """Set `closed_at` under CAS -- the structural close primitive, and nothing more.

    This decides NOTHING. It is not close-on-accept, close-on-reject, close-on-expiry or any other
    workflow rule; 66D-D05 section 7 defers every transition semantic, so no caller inside BE1
    invokes this automatically. Setting `closed_at` carries no outcome meaning whatsoever
    (D05-R7): it does not mean ACCEPTED, REJECTED, EXPIRED, ARCHIVED, that a ProductOwnerDecision
    exists, that QA completed, or that the submission reached a terminal status.

    Guarded by `closed_at IS NULL`, so closing is not repeatable and there is no reopen primitive
    here (reopen is deferred, D05-R10). Returns None on a stale version or an already-closed task.
    """
    return _row(
        await conn.fetchrow(
            """
            UPDATE delivery_review_tasks
            SET closed_at=statement_timestamp(),
                row_version=row_version + 1,
                updated_at=statement_timestamp()
            WHERE delivery_review_task_id=$1 AND row_version=$2 AND closed_at IS NULL
            RETURNING *
            """,
            delivery_review_task_id,
            expected_row_version,
        )
    )


async def list_review_tasks(
    conn: asyncpg.Connection, delivery_submission_id: str
) -> list[dict[str, Any]]:
    """Every review task for a submission, active and closed, oldest first."""
    return [
        dict(r)
        for r in await conn.fetch(
            """
            SELECT * FROM delivery_review_tasks
            WHERE delivery_submission_id=$1
            ORDER BY created_at, delivery_review_task_id
            """,
            delivery_submission_id,
        )
    ]


# ---- DeliveryReviewAction (append-only) ---------------------------------------------------------


async def append_review_action(
    conn: asyncpg.Connection,
    *,
    delivery_submission_id: str,
    delivery_review_task_id: str,
    action_type: str,
    actor_ref: str,
    idempotency_key: str,
    actor_role: str | None = None,
    reason: str | None = None,
    requested_scope: str | None = None,
    previous_qa_ref: str | None = None,
    audit_event_id: str | None = None,
) -> dict[str, Any]:
    """Append one recorded Review Gate Action. There is no counterpart update or delete.

    A duplicate `(delivery_submission_id, idempotency_key)` raises asyncpg.UniqueViolationError --
    durable duplicate prevention, which is BE1's whole idempotency responsibility. Turning that
    into a replayed HTTP response is Step 66D-BE3.

    An ACCEPT or REJECT action does NOT create a ProductOwnerDecision here. Recording the two
    atomically in one transaction is Step 66D-BE3 action policy; BE1 only provides the two
    primitives it will compose.
    """
    model.assert_review_action_type(action_type)
    record = await conn.fetchrow(
        """
        INSERT INTO delivery_review_actions
          (delivery_submission_id, delivery_review_task_id, action_type, actor_ref, actor_role,
           reason, requested_scope, previous_qa_ref, idempotency_key, audit_event_id)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
        RETURNING *
        """,
        delivery_submission_id,
        delivery_review_task_id,
        action_type,
        actor_ref,
        actor_role,
        reason,
        requested_scope,
        previous_qa_ref,
        idempotency_key,
        audit_event_id,
    )
    assert record is not None
    return dict(record)


async def list_review_actions(
    conn: asyncpg.Connection, delivery_submission_id: str
) -> list[dict[str, Any]]:
    """The append-only action history for a submission, oldest first. Nothing is ever hidden."""
    return [
        dict(r)
        for r in await conn.fetch(
            """
            SELECT * FROM delivery_review_actions
            WHERE delivery_submission_id=$1
            ORDER BY created_at, review_action_id
            """,
            delivery_submission_id,
        )
    ]


# ---- ProductOwnerDecision (append-only, supersedable) -------------------------------------------


async def append_decision(
    conn: asyncpg.Connection,
    *,
    delivery_submission_id: str,
    decision_type: str,
    decision_reason: str,
    decided_by_actor: str,
    idempotency_key: str,
    delivery_review_task_id: str | None = None,
    supersedes_decision_id: str | None = None,
    evidence_reviewed: str = "[]",
    audit_event_id: str | None = None,
) -> dict[str, Any]:
    """Append a Product Owner Final Decision, optionally superseding an earlier one.

    Never updates or deletes an existing row (D02-R1, D02-R3): a correction is a NEW row whose
    `supersedes_decision_id` names its predecessor, and the superseded row stays queryable
    forever.

    `decision_version` is DERIVED from the locked predecessor, never caller-supplied. Integrity
    checks, and where each is guaranteed:

      self-supersession        DB CHECK chk_pod_no_self_supersession, plus the fact that a row
                               cannot reference its own not-yet-generated id
      cross-submission         REPOSITORY guarantee (below): a predecessor belonging to another
                               submission is rejected before any write
      forked history           DB partial unique uq_pod_supersedes -- at most one successor
      cycle                    structurally impossible: the chain is linear (one successor each)
                               and versions strictly increase, so no row can precede itself
      duplicate version        DB unique uq_pod_submission_version
    """
    model.assert_po_decision_type(decision_type)

    decision_version = 1
    if supersedes_decision_id is not None:
        predecessor = _row(
            await conn.fetchrow(
                "SELECT * FROM product_owner_decisions WHERE decision_id=$1 FOR UPDATE",
                supersedes_decision_id,
            )
        )
        if predecessor is None:
            raise ValueError("supersedes_decision_id does not exist")
        if str(predecessor["delivery_submission_id"]) != str(delivery_submission_id):
            raise ValueError("cross-submission supersession is not permitted")
        decision_version = int(predecessor["decision_version"]) + 1

    record = await conn.fetchrow(
        """
        INSERT INTO product_owner_decisions
          (delivery_submission_id, delivery_review_task_id, decision_type, decision_reason,
           decided_by_actor, evidence_reviewed, supersedes_decision_id, decision_version,
           idempotency_key, audit_event_id)
        VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7,$8,$9,$10)
        RETURNING *
        """,
        delivery_submission_id,
        delivery_review_task_id,
        decision_type,
        decision_reason,
        decided_by_actor,
        evidence_reviewed,
        supersedes_decision_id,
        decision_version,
        idempotency_key,
        audit_event_id,
    )
    assert record is not None
    return dict(record)


async def list_decisions(
    conn: asyncpg.Connection, delivery_submission_id: str
) -> list[dict[str, Any]]:
    """Full decision history for a submission INCLUDING superseded rows, oldest version first."""
    return [
        dict(r)
        for r in await conn.fetch(
            """
            SELECT * FROM product_owner_decisions
            WHERE delivery_submission_id=$1
            ORDER BY decision_version
            """,
            delivery_submission_id,
        )
    ]


async def get_effective_decision(
    conn: asyncpg.Connection, delivery_submission_id: str
) -> dict[str, Any] | None:
    """The decision currently in force: highest version, not itself superseded (ARCH1 section 4).

    Returns None when the submission has no decision at all. No decision is NOT acceptance.
    """
    return model.effective_decision(await list_decisions(conn, delivery_submission_id))


# ---- AcceptanceFollowUpItem ---------------------------------------------------------------------


async def create_follow_up_item(
    conn: asyncpg.Connection,
    *,
    decision_id: str,
    description: str,
    owner_actor_ref: str,
    severity: str,
    blocking: bool = False,
    due_at: datetime | None = None,
    status: str = "OPEN",
    evidence_refs: str = "[]",
) -> dict[str, Any]:
    """Create a follow-up against a decision.

    BE1 stores `blocking` and enforces nothing about it. "ACCEPTED_WITH_FOLLOW_UP accepts only
    blocking = false" is Step 66D-BE3 action/transaction policy (409
    BLOCKING_FOLLOW_UP_REQUIRES_CHANGES) and must not be implemented early here, by trigger,
    constraint or code.
    """
    model.assert_follow_up_status(status)
    record = await conn.fetchrow(
        """
        INSERT INTO acceptance_follow_up_items
          (decision_id, description, owner_actor_ref, severity, blocking, due_at, status,
           evidence_refs)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb)
        RETURNING *
        """,
        decision_id,
        description,
        owner_actor_ref,
        severity,
        blocking,
        due_at,
        status,
        evidence_refs,
    )
    assert record is not None
    return dict(record)


async def list_follow_up_items(conn: asyncpg.Connection, decision_id: str) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in await conn.fetch(
            """
            SELECT * FROM acceptance_follow_up_items
            WHERE decision_id=$1
            ORDER BY created_at, follow_up_item_id
            """,
            decision_id,
        )
    ]
