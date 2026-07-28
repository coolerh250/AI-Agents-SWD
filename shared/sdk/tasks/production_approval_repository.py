"""Step 66C.4-BE3-R1 (finding M-1 closure) -- production-action approval repository.

Transaction-aware asyncpg repository over production_action_approvals (migration 035). Every state
transition is a guarded CAS UPDATE ... RETURNING that returns the row on success and None when the
guard did not hold. PostgreSQL statement_timestamp() is the authoritative clock for validity -- never
a Python local clock. All methods take the CALLER's asyncpg connection and run inside the caller's
transaction (never a separate connection-per-call, so `resolve_and_consume_approval` can compose
atomically with `authorization_repository.consume` inside authorization_service.consume -- the same
composability requirement already solved for `replay_request_repository.replay_dead_row`).

Scope enforcement mirrors BE3-A-C2: team_id/project_id are NOT NULL on the row, and every
actor-facing predicate is exact null-safe equality (`IS NOT DISTINCT FROM`), so a NULL caller scope
matches nothing (fail-closed) and a mismatched scope matches nothing.

This module performs NO resume/replay execution, exposes NO HTTP route, and starts NO scheduler.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import asyncpg

# Exact null-safe scope predicate (BE3-A-C2 convention). {a} = scope_team, {b} = scope_project.
_SCOPE = "team_id IS NOT DISTINCT FROM {a}::uuid AND project_id IS NOT DISTINCT FROM {b}::uuid"


def _row(record: asyncpg.Record | None) -> dict[str, Any] | None:
    return dict(record) if record is not None else None


async def db_now(conn: asyncpg.Connection) -> datetime:
    return await conn.fetchval("SELECT statement_timestamp()")


async def insert_approval(
    conn: asyncpg.Connection,
    *,
    action_type: str,
    resource_type: str,
    resource_id: str,
    team_id: str,
    project_id: str,
    resource_state_version: str,
    granted_by: str,
    granted_role: str,
    expires_at: datetime,
    idempotency_key: str,
    reason_code: str | None = None,
) -> dict[str, Any]:
    """Insert a new granted approval. A duplicate idempotency_key raises
    asyncpg.UniqueViolationError (the caller maps that to an idempotent re-confirm)."""
    record = await conn.fetchrow(
        """
        INSERT INTO production_action_approvals
          (action_type, resource_type, resource_id, team_id, project_id, resource_state_version,
           granted_by, granted_role, expires_at, idempotency_key, reason_code)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
        RETURNING *
        """,
        action_type,
        resource_type,
        resource_id,
        team_id,
        project_id,
        resource_state_version,
        granted_by,
        granted_role,
        expires_at,
        idempotency_key,
        reason_code,
    )
    assert record is not None
    return dict(record)


async def get_approval_by_idempotency_key(
    conn: asyncpg.Connection, idempotency_key: str
) -> dict[str, Any] | None:
    return _row(
        await conn.fetchrow(
            "SELECT * FROM production_action_approvals WHERE idempotency_key=$1", idempotency_key
        )
    )


async def get_approval(
    conn: asyncpg.Connection,
    approval_id: str,
    *,
    scope_team_id: str | None = None,
    scope_project_id: str | None = None,
) -> dict[str, Any] | None:
    """Read one approval, scoped. A cross-scope id reads nothing (None)."""
    return _row(
        await conn.fetchrow(
            f"""
            SELECT * FROM production_action_approvals
            WHERE approval_id=$1 AND {_SCOPE.format(a="$2", b="$3")}
            """,
            approval_id,
            scope_team_id,
            scope_project_id,
        )
    )


async def revoke_approval(
    conn: asyncpg.Connection,
    approval_id: str,
    *,
    revoked_by: str,
    reason_code: str | None,
    scope_team_id: str | None = None,
    scope_project_id: str | None = None,
) -> dict[str, Any] | None:
    """CAS granted (unconsumed/unrevoked) -> revoked, scoped. A consumed approval can never be
    revoked (guarded by consumed_at IS NULL)."""
    return _row(
        await conn.fetchrow(
            f"""
            UPDATE production_action_approvals
            SET state='revoked', revoked_at=statement_timestamp(), revoked_by=$2,
                revocation_reason_code=$3, updated_at=statement_timestamp()
            WHERE approval_id=$1 AND state='granted'
              AND consumed_at IS NULL AND revoked_at IS NULL
              AND {_SCOPE.format(a="$4", b="$5")}
            RETURNING *
            """,
            approval_id,
            revoked_by,
            reason_code,
            scope_team_id,
            scope_project_id,
        )
    )


async def resolve_and_consume_approval(
    conn: asyncpg.Connection,
    reference: str | None,
    *,
    action_type: str,
    resource_type: str,
    resource_id: str,
    team_id: str,
    project_id: str,
    resource_state_version: str,
    consumed_by: str,
    consumed_by_authorization_id: str,
) -> tuple[dict[str, Any] | None, str]:
    """Resolve `reference` (a `production_action_approvals.approval_id`) against the authoritative
    registry and, if and only if EVERY binding check passes, atomically consume it (single-use) in
    THIS transaction -- so an invalid/stale/expired/revoked/wrong-scope/wrong-resource/wrong-action
    approval can NEVER be left half-consumed and a consumed authorization NEVER exists without a
    validly-consumed approval backing it (Step 66C.4-BE3-R1, finding M-1 closure).

    Locks the approval row (SELECT ... FOR UPDATE) for the remainder of THIS transaction before any
    check, so no concurrent caller can revoke or consume it out from under this evaluation -- the
    informational checks below and the final CAS UPDATE always observe the SAME locked row.

    Returns (row, "ok") on success, or (None, reason_code) on any failure -- reason_code is one of
    production_approval_model.REASON_CODES (invalid_reference | not_found | already_consumed |
    already_revoked | expired | wrong_action | wrong_resource | wrong_scope | stale_state |
    conflict). Never mutates anything on a failure path.
    """
    if not reference:
        return None, "not_found"
    try:
        approval_id = str(uuid.UUID(reference))
    except (ValueError, AttributeError, TypeError):
        return None, "invalid_reference"

    row = await conn.fetchrow(
        "SELECT * FROM production_action_approvals WHERE approval_id=$1 FOR UPDATE",
        approval_id,
    )
    if row is None:
        return None, "not_found"
    row = dict(row)

    if row["consumed_at"] is not None:
        return None, "already_consumed"
    if row["revoked_at"] is not None:
        return None, "already_revoked"
    now = await db_now(conn)
    if row["expires_at"] <= now:
        return None, "expired"
    if row["action_type"] != action_type:
        return None, "wrong_action"
    if row["resource_type"] != resource_type or str(row["resource_id"]) != str(resource_id):
        return None, "wrong_resource"
    if str(row["team_id"]) != str(team_id) or str(row["project_id"]) != str(project_id):
        return None, "wrong_scope"
    if row["resource_state_version"] != resource_state_version:
        return None, "stale_state"

    updated = await conn.fetchrow(
        """
        UPDATE production_action_approvals
        SET state='consumed', consumed_at=statement_timestamp(), consumed_by=$2,
            consumed_by_authorization_id=$3, updated_at=statement_timestamp()
        WHERE approval_id=$1 AND state='granted'
          AND consumed_at IS NULL AND revoked_at IS NULL
          AND expires_at > statement_timestamp()
          AND action_type=$4 AND resource_type=$5 AND resource_id=$6
          AND team_id=$7::uuid AND project_id=$8::uuid
          AND resource_state_version=$9
        RETURNING *
        """,
        approval_id,
        consumed_by,
        consumed_by_authorization_id,
        action_type,
        resource_type,
        resource_id,
        team_id,
        project_id,
        resource_state_version,
    )
    if updated is None:
        # Unreachable in practice (the row has been locked continuously since the SELECT above, so
        # nothing could have changed it) -- kept as a defensive, non-mutating fallback.
        return None, "conflict"
    return dict(updated), "ok"
