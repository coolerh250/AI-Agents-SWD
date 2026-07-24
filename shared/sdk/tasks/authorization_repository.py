"""Step 66C.4-BE3-A -- durable resume/replay authorization repository.

Transaction-aware asyncpg repository over resume_replay_authorizations (migration 032). Every state
transition is a guarded CAS UPDATE ... RETURNING that returns the row on success and None when the
guard did not hold (the CAS lost). PostgreSQL statement_timestamp() is the authoritative clock for
validity -- never a Python local clock.

This module performs NO resume/replay execution, calls NO dead-outbox replay adapter, exposes NO HTTP route, and
starts NO scheduler or loop. `expire_due_authorizations` is a one-shot repository operation for a
caller/test to invoke; it is not a runtime loop.

All methods take the CALLER's asyncpg connection and run inside the caller's transaction (they do
not begin, commit, or close it), so an authorization transition and its audit/outbox row can commit
atomically under the caller's boundary.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import asyncpg

_COLUMNS = "*"


def _row(record: asyncpg.Record | None) -> dict[str, Any] | None:
    return dict(record) if record is not None else None


async def db_now(conn: asyncpg.Connection) -> datetime:
    """The DB statement clock -- the authoritative 'now' for state projection/validity."""
    return await conn.fetchval("SELECT statement_timestamp()")


async def create_request(
    conn: asyncpg.Connection,
    *,
    action_type: str,
    resource_type: str,
    resource_id: str,
    requested_by: str,
    requested_role: str,
    resource_state_version: str,
    expires_at: datetime,
    idempotency_key: str,
    team_id: str | None = None,
    project_id: str | None = None,
    production_effect: bool = False,
    production_approval_reference: str | None = None,
) -> dict[str, Any]:
    """Insert a new pending authorization request. The uq_rra_active_request partial unique index
    rejects a second ACTIVE request for the same (action_type, resource_id); the idempotency_key
    unique constraint rejects a duplicate key. Both surface as asyncpg.UniqueViolationError."""
    record = await conn.fetchrow(
        f"""
        INSERT INTO resume_replay_authorizations
          (action_type, resource_type, resource_id, team_id, project_id, requested_by,
           requested_role, resource_state_version, expires_at, idempotency_key,
           production_effect, production_approval_reference)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
        RETURNING {_COLUMNS}
        """,
        action_type,
        resource_type,
        resource_id,
        team_id,
        project_id,
        requested_by,
        requested_role,
        resource_state_version,
        expires_at,
        idempotency_key,
        production_effect,
        production_approval_reference,
    )
    assert record is not None  # INSERT ... RETURNING always yields a row on success
    return dict(record)


async def get_authorization(
    conn: asyncpg.Connection, authorization_id: str
) -> dict[str, Any] | None:
    return _row(
        await conn.fetchrow(
            f"SELECT {_COLUMNS} FROM resume_replay_authorizations WHERE authorization_id=$1",
            authorization_id,
        )
    )


async def get_active_by_resource(
    conn: asyncpg.Connection, *, action_type: str, resource_id: str
) -> dict[str, Any] | None:
    return _row(
        await conn.fetchrow(
            f"""
            SELECT {_COLUMNS} FROM resume_replay_authorizations
            WHERE action_type=$1 AND resource_id=$2
              AND decision IN ('pending','authorized')
              AND consumed_at IS NULL AND revoked_at IS NULL AND expired_at IS NULL
            """,
            action_type,
            resource_id,
        )
    )


async def approve(
    conn: asyncpg.Connection,
    authorization_id: str,
    *,
    decided_by: str,
    decided_role: str,
    reason_code: str | None,
    policy_result: str,
    policy_version: str,
) -> dict[str, Any] | None:
    """CAS pending -> authorized. The chk_rra_replay_two_person DB constraint additionally rejects a
    replay approval by the requester (defense in depth behind the policy service)."""
    return _row(
        await conn.fetchrow(
            f"""
            UPDATE resume_replay_authorizations
            SET decision='authorized', decided_by=$2, decided_role=$3,
                decided_at=statement_timestamp(), decision_reason_code=$4,
                policy_result=$5, policy_version=$6, updated_at=statement_timestamp()
            WHERE authorization_id=$1 AND decision='pending' AND expired_at IS NULL
            RETURNING {_COLUMNS}
            """,
            authorization_id,
            decided_by,
            decided_role,
            reason_code,
            policy_result,
            policy_version,
        )
    )


async def reject(
    conn: asyncpg.Connection,
    authorization_id: str,
    *,
    decided_by: str,
    decided_role: str,
    reason_code: str | None,
) -> dict[str, Any] | None:
    """CAS pending -> rejected."""
    return _row(
        await conn.fetchrow(
            f"""
            UPDATE resume_replay_authorizations
            SET decision='rejected', decided_by=$2, decided_role=$3,
                decided_at=statement_timestamp(), decision_reason_code=$4,
                updated_at=statement_timestamp()
            WHERE authorization_id=$1 AND decision='pending' AND expired_at IS NULL
            RETURNING {_COLUMNS}
            """,
            authorization_id,
            decided_by,
            decided_role,
            reason_code,
        )
    )


async def cancel(
    conn: asyncpg.Connection,
    authorization_id: str,
    *,
    decided_by: str,
    decided_role: str,
    reason_code: str | None,
) -> dict[str, Any] | None:
    """CAS pending -> canceled."""
    return _row(
        await conn.fetchrow(
            f"""
            UPDATE resume_replay_authorizations
            SET decision='canceled', decided_by=$2, decided_role=$3,
                decided_at=statement_timestamp(), decision_reason_code=$4,
                updated_at=statement_timestamp()
            WHERE authorization_id=$1 AND decision='pending' AND expired_at IS NULL
            RETURNING {_COLUMNS}
            """,
            authorization_id,
            decided_by,
            decided_role,
            reason_code,
        )
    )


async def revoke(
    conn: asyncpg.Connection,
    authorization_id: str,
    *,
    revoked_by: str,
    reason_code: str | None,
) -> dict[str, Any] | None:
    """CAS authorized (unconsumed/unrevoked/unexpired) -> revoked. A consumed authorization can
    never be revoked (guarded by consumed_at IS NULL)."""
    return _row(
        await conn.fetchrow(
            f"""
            UPDATE resume_replay_authorizations
            SET revoked_at=statement_timestamp(), revoked_by=$2, revocation_reason_code=$3,
                updated_at=statement_timestamp()
            WHERE authorization_id=$1 AND decision='authorized'
              AND consumed_at IS NULL AND revoked_at IS NULL AND expired_at IS NULL
            RETURNING {_COLUMNS}
            """,
            authorization_id,
            revoked_by,
            reason_code,
        )
    )


async def consume(
    conn: asyncpg.Connection,
    authorization_id: str,
    *,
    consumed_by: str,
    resource_state_version: str,
) -> dict[str, Any] | None:
    """Single-use atomic CAS. Succeeds only when the authorization is authorized, unconsumed,
    unrevoked, unexpired (expired_at IS NULL AND expires_at > statement_timestamp()), and its
    resource_state_version still matches. Returns the row on success, None on any failed guard.
    Under concurrency EXACTLY ONE consume wins (this is a single DB CAS, not distributed
    exactly-once)."""
    return _row(
        await conn.fetchrow(
            f"""
            UPDATE resume_replay_authorizations
            SET consumed_at=statement_timestamp(), consumed_by=$2, updated_at=statement_timestamp()
            WHERE authorization_id=$1 AND decision='authorized'
              AND consumed_at IS NULL AND revoked_at IS NULL AND expired_at IS NULL
              AND expires_at > statement_timestamp()
              AND resource_state_version=$3
            RETURNING {_COLUMNS}
            """,
            authorization_id,
            consumed_by,
            resource_state_version,
        )
    )


async def expire_due_authorizations(conn: asyncpg.Connection, *, limit: int = 500) -> int:
    """One-shot: mark unresolved authorizations whose deadline has passed as expired (durable
    terminal marker). NOT a scheduler/loop. Returns the number of rows expired."""
    tag = await conn.execute(
        """
        UPDATE resume_replay_authorizations
        SET expired_at=statement_timestamp(), updated_at=statement_timestamp()
        WHERE decision IN ('pending','authorized')
          AND consumed_at IS NULL AND revoked_at IS NULL AND expired_at IS NULL
          AND expires_at <= statement_timestamp()
          AND authorization_id IN (
            SELECT authorization_id FROM resume_replay_authorizations
            WHERE decision IN ('pending','authorized')
              AND consumed_at IS NULL AND revoked_at IS NULL AND expired_at IS NULL
              AND expires_at <= statement_timestamp()
            LIMIT $1
          )
        """,
        limit,
    )
    try:
        return int(tag.split()[-1])
    except (ValueError, IndexError, AttributeError):
        return 0
