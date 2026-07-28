"""Step 66C.4-BE3-B -- operator-controlled resume request repository.

Transaction-aware asyncpg repository over resume_requests (migration 033) plus the guarded CAS
primitives on operator_clarification_requests / operator_tasks that the resume flow needs. Every
mutation is a guarded CAS UPDATE ... RETURNING (row on success, None when the guard did not hold).
PostgreSQL statement_timestamp() is the authoritative clock; row locks (SELECT ... FOR UPDATE) are
taken by the caller's transaction, never a Python clock or an in-memory guard.

Scope enforcement (carried forward from BE3-A-C2): every actor-facing read/transition binds the
actor's team/project scope with EXACT null-safe equality; team_id/project_id are NOT NULL on the
row, so a NULL/cross scope matches nothing (fail-closed). `expire_due_requests` is the only unscoped
operation -- a non-actor-facing maintenance scan.

This module performs NO orchestrator call, NO resume execution, NO event publish, and exposes NO
HTTP route. All methods take the CALLER's asyncpg connection and run inside the caller's transaction.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import asyncpg

# Exact null-safe scope predicate (BE3-A-C2). {a} = scope_team, {b} = scope_project.
_SCOPE = "team_id IS NOT DISTINCT FROM {a}::uuid AND project_id IS NOT DISTINCT FROM {b}::uuid"


def _row(record: asyncpg.Record | None) -> dict[str, Any] | None:
    return dict(record) if record is not None else None


async def db_now(conn: asyncpg.Connection) -> datetime:
    return await conn.fetchval("SELECT statement_timestamp()")


# ---- Locks / authoritative reads ---------------------------------------------------------------


async def lock_clarification(
    conn: asyncpg.Connection, clarification_id: str
) -> dict[str, Any] | None:
    """Lock and read the clarification row (FOR UPDATE) for the caller's transaction."""
    return _row(
        await conn.fetchrow(
            "SELECT * FROM operator_clarification_requests WHERE id=$1 FOR UPDATE",
            clarification_id,
        )
    )


async def lock_task(conn: asyncpg.Connection, task_id: str) -> dict[str, Any] | None:
    return _row(
        await conn.fetchrow(
            "SELECT * FROM operator_tasks WHERE id=$1 FOR UPDATE",
            task_id,
        )
    )


# ---- Clarification-level authoritative markers (migration 031 columns; NOT duplicated) ----------


async def claim_clarification_resume_requested(
    conn: asyncpg.Connection,
    clarification_id: str,
    *,
    requested_by: str,
) -> dict[str, Any] | None:
    """CAS resume_requested_at IS NULL -> now(). This is the atomic guard that lets exactly one
    resume request become active for a clarification. Returns None if a request is already active
    (marker already set)."""
    return _row(
        await conn.fetchrow(
            """
            UPDATE operator_clarification_requests
            SET resume_requested_at=statement_timestamp(), resume_requested_by=$2,
                updated_at=statement_timestamp()
            WHERE id=$1 AND resume_requested_at IS NULL
            RETURNING *
            """,
            clarification_id,
            requested_by,
        )
    )


async def mark_clarification_resume_authorized(
    conn: asyncpg.Connection, clarification_id: str
) -> dict[str, Any] | None:
    """CAS resume_authorized_at IS NULL -> now(), guarded by resume_eligible_at IS NOT NULL (the DB
    chk_ocr_resume_authorized_requires_eligible constraint enforces this too)."""
    return _row(
        await conn.fetchrow(
            """
            UPDATE operator_clarification_requests
            SET resume_authorized_at=statement_timestamp(), updated_at=statement_timestamp()
            WHERE id=$1 AND resume_authorized_at IS NULL AND resume_eligible_at IS NOT NULL
            RETURNING *
            """,
            clarification_id,
        )
    )


async def release_clarification_resume_markers(
    conn: asyncpg.Connection, clarification_id: str
) -> None:
    """Clear the live resume markers so the clarification can be requested again after a terminal,
    non-resumed request (cancel/reject/expire/fail). resume_eligible_at is preserved (eligibility is
    durable). The full history stays in resume_requests + the audit outbox; these columns are a live
    pointer to the CURRENT active request, not an audit log."""
    await conn.execute(
        """
        UPDATE operator_clarification_requests
        SET resume_requested_at=NULL, resume_requested_by=NULL, resume_authorized_at=NULL,
            updated_at=statement_timestamp()
        WHERE id=$1
        """,
        clarification_id,
    )


# ---- resume_requests -----------------------------------------------------------------------------


async def insert_resume_request(
    conn: asyncpg.Connection,
    *,
    authorization_id: str,
    clarification_id: str,
    task_id: str,
    team_id: str,
    project_id: str,
    resource_state_version: str,
    requested_by: str,
    idempotency_key: str,
    workflow_id: str | None = None,
) -> dict[str, Any]:
    """Insert a new resume request in state authorization_pending. The uq_rr_active_per_clarification
    partial unique index rejects a second active request; a duplicate idempotency_key raises
    asyncpg.UniqueViolationError."""
    record = await conn.fetchrow(
        """
        INSERT INTO resume_requests
          (authorization_id, clarification_id, task_id, workflow_id, team_id, project_id,
           resource_state_version, requested_by, idempotency_key)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
        RETURNING *
        """,
        authorization_id,
        clarification_id,
        task_id,
        workflow_id,
        team_id,
        project_id,
        resource_state_version,
        requested_by,
        idempotency_key,
    )
    assert record is not None
    return dict(record)


async def get_resume_request(
    conn: asyncpg.Connection,
    resume_request_id: str,
    *,
    scope_team_id: str | None = None,
    scope_project_id: str | None = None,
) -> dict[str, Any] | None:
    """Read one resume request, scoped. A NULL/cross scope reads nothing (None)."""
    return _row(
        await conn.fetchrow(
            f"""
            SELECT * FROM resume_requests
            WHERE resume_request_id=$1 AND {_SCOPE.format(a="$2", b="$3")}
            """,
            resume_request_id,
            scope_team_id,
            scope_project_id,
        )
    )


async def get_request_by_idempotency_key(
    conn: asyncpg.Connection, idempotency_key: str
) -> dict[str, Any] | None:
    return _row(
        await conn.fetchrow(
            "SELECT * FROM resume_requests WHERE idempotency_key=$1",
            idempotency_key,
        )
    )


async def get_resume_request_internal(
    conn: asyncpg.Connection, resume_request_id: str
) -> dict[str, Any] | None:
    """Unscoped read for INTERNAL orchestrator-reconciliation confirmation ONLY (not actor-facing).
    Never exposed to an external caller; the confirmation path has no team/project scope."""
    return _row(
        await conn.fetchrow(
            "SELECT * FROM resume_requests WHERE resume_request_id=$1",
            resume_request_id,
        )
    )


async def lock_resume_request(
    conn: asyncpg.Connection,
    resume_request_id: str,
    *,
    scope_team_id: str | None = None,
    scope_project_id: str | None = None,
) -> dict[str, Any] | None:
    """Lock and read one resume request (FOR UPDATE), scoped."""
    return _row(
        await conn.fetchrow(
            f"""
            SELECT * FROM resume_requests
            WHERE resume_request_id=$1 AND {_SCOPE.format(a="$2", b="$3")}
            FOR UPDATE
            """,
            resume_request_id,
            scope_team_id,
            scope_project_id,
        )
    )


async def transition_to_authorized(
    conn: asyncpg.Connection,
    resume_request_id: str,
    *,
    scope_team_id: str | None = None,
    scope_project_id: str | None = None,
) -> dict[str, Any] | None:
    """CAS authorization_pending -> authorized (sets authorized_at)."""
    return _row(
        await conn.fetchrow(
            f"""
            UPDATE resume_requests
            SET state='authorized', authorized_at=statement_timestamp(),
                updated_at=statement_timestamp()
            WHERE resume_request_id=$1 AND state='authorization_pending'
              AND {_SCOPE.format(a="$2", b="$3")}
            RETURNING *
            """,
            resume_request_id,
            scope_team_id,
            scope_project_id,
        )
    )


async def transition_to_rejected(
    conn: asyncpg.Connection,
    resume_request_id: str,
    *,
    reason_code: str,
    scope_team_id: str | None = None,
    scope_project_id: str | None = None,
) -> dict[str, Any] | None:
    """CAS authorization_pending -> rejected."""
    return _row(
        await conn.fetchrow(
            f"""
            UPDATE resume_requests
            SET state='rejected', failure_reason_code=$2, updated_at=statement_timestamp()
            WHERE resume_request_id=$1 AND state='authorization_pending'
              AND {_SCOPE.format(a="$3", b="$4")}
            RETURNING *
            """,
            resume_request_id,
            reason_code,
            scope_team_id,
            scope_project_id,
        )
    )


async def transition_to_canceled(
    conn: asyncpg.Connection,
    resume_request_id: str,
    *,
    scope_team_id: str | None = None,
    scope_project_id: str | None = None,
) -> dict[str, Any] | None:
    """CAS authorization_pending -> canceled (an Operator may only cancel a still-pending request)."""
    return _row(
        await conn.fetchrow(
            f"""
            UPDATE resume_requests
            SET state='canceled', canceled_at=statement_timestamp(),
                updated_at=statement_timestamp()
            WHERE resume_request_id=$1 AND state='authorization_pending'
              AND {_SCOPE.format(a="$2", b="$3")}
            RETURNING *
            """,
            resume_request_id,
            scope_team_id,
            scope_project_id,
        )
    )


async def transition_to_execution_pending(
    conn: asyncpg.Connection,
    resume_request_id: str,
    *,
    command_id: str,
    scope_team_id: str | None = None,
    scope_project_id: str | None = None,
) -> dict[str, Any] | None:
    """CAS authorized -> execution_pending (records the durable command id + execution_requested_at).
    Under concurrency EXACTLY ONE preparer wins this CAS."""
    return _row(
        await conn.fetchrow(
            f"""
            UPDATE resume_requests
            SET state='execution_pending', execution_requested_at=statement_timestamp(),
                command_id=$2, updated_at=statement_timestamp()
            WHERE resume_request_id=$1 AND state='authorized'
              AND {_SCOPE.format(a="$3", b="$4")}
            RETURNING *
            """,
            resume_request_id,
            command_id,
            scope_team_id,
            scope_project_id,
        )
    )


async def confirm_resumed(
    conn: asyncpg.Connection,
    resume_request_id: str,
    *,
    command_id: str,
) -> dict[str, Any] | None:
    """Internal confirmation: execution_pending -> resumed, guarded by a matching command_id.
    Idempotent: a duplicate confirmation returns None (no second transition). Unscoped: this is an
    internal orchestrator-reconciliation op, not an actor-facing read/transition."""
    return _row(
        await conn.fetchrow(
            """
            UPDATE resume_requests
            SET state='resumed', resumed_at=statement_timestamp(), updated_at=statement_timestamp()
            WHERE resume_request_id=$1 AND state='execution_pending' AND command_id=$2
            RETURNING *
            """,
            resume_request_id,
            command_id,
        )
    )


async def confirm_failed(
    conn: asyncpg.Connection,
    resume_request_id: str,
    *,
    command_id: str,
    reason_code: str,
) -> dict[str, Any] | None:
    """Internal confirmation: execution_pending -> failed, guarded by a matching command_id.
    Idempotent duplicate -> None. A resumed request can never become failed (state guard)."""
    return _row(
        await conn.fetchrow(
            """
            UPDATE resume_requests
            SET state='failed', failed_at=statement_timestamp(), failure_reason_code=$3,
                updated_at=statement_timestamp()
            WHERE resume_request_id=$1 AND state='execution_pending' AND command_id=$2
            RETURNING *
            """,
            resume_request_id,
            command_id,
            reason_code,
        )
    )


async def expire_due_requests(
    conn: asyncpg.Connection, *, before: datetime, limit: int = 500
) -> int:
    """One-shot maintenance: mark still-pending/authorized requests whose bound authorization has
    expired as expired. NOT a scheduler/loop and NOT actor-facing (no scope filter). `before` is a
    DB-sourced timestamp supplied by the caller. Returns the number of rows expired."""
    tag = await conn.execute(
        """
        UPDATE resume_requests rr
        SET state='expired', expired_at=statement_timestamp(), updated_at=statement_timestamp()
        FROM resume_replay_authorizations a
        WHERE rr.authorization_id = a.authorization_id
          AND rr.state IN ('authorization_pending','authorized')
          AND a.expires_at <= $1
          AND rr.resume_request_id IN (
            SELECT resume_request_id FROM resume_requests
            WHERE state IN ('authorization_pending','authorized')
            LIMIT $2
          )
        """,
        before,
        limit,
    )
    try:
        return int(tag.split()[-1])
    except (ValueError, IndexError, AttributeError):
        return 0
