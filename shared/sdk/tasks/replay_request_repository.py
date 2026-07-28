"""Step 66C.4-BE3-C -- authorized dead-event replay request repository.

Transaction-aware asyncpg repository over replay_requests (migration 034) plus the guarded CAS
primitives on clarification_lifecycle_outbox that the replay flow needs. Every mutation is a
guarded CAS UPDATE ... RETURNING (row on success, None when the guard did not hold).
PostgreSQL statement_timestamp() is the authoritative clock; row locks (SELECT ... FOR UPDATE) are
taken by the caller's transaction, never a Python clock or an in-memory guard.

Scope enforcement (carried forward from BE3-A-C2 / BE3-B): every actor-facing read/transition binds
the actor's team/project scope with EXACT null-safe equality; team_id/project_id are NOT NULL on the
row, so a NULL/cross scope matches nothing (fail-closed). `expire_due_replay_requests` is the only
unscoped operation -- a non-actor-facing maintenance scan.

`replay_dead_row` is a NEW, transaction-aware internal replay adapter: unlike
`ClarificationOutboxRelay.replay_dead` (which always owns and commits its OWN transaction, so it
cannot be composed into a caller's transaction alongside an authorization consume), this function
takes the CALLER's connection and runs INSIDE the caller's transaction -- never begins, commits, or
rolls back anything itself -- so a replay execution's authorization-consume + dead-row mutation +
audit evidence commit or roll back TOGETHER, atomically. It is functionally equivalent to
ClarificationOutboxRelay.replay_dead (same guard, same plan_replay_state preserved-attempts
semantics, same preserved event_id/idempotency_key/payload/created_at) plus an additional
resource_state_version CAS guard.

This module performs NO real publish, NO orchestrator call, exposes NO HTTP route, and starts NO
scheduler or loop.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import asyncpg

from shared.sdk.tasks.lifecycle_outbox import plan_replay_state
from shared.sdk.tasks.replay_request_model import dead_episode_state_version

# Exact null-safe scope predicate (BE3-A-C2 / BE3-B). {a} = scope_team, {b} = scope_project.
_SCOPE = "team_id IS NOT DISTINCT FROM {a}::uuid AND project_id IS NOT DISTINCT FROM {b}::uuid"


def _row(record: asyncpg.Record | None) -> dict[str, Any] | None:
    return dict(record) if record is not None else None


async def db_now(conn: asyncpg.Connection) -> datetime:
    return await conn.fetchval("SELECT statement_timestamp()")


# ---- Locks / authoritative reads on the dead outbox row ---------------------------------------


async def lock_outbox_event(conn: asyncpg.Connection, event_id: str) -> dict[str, Any] | None:
    """Lock and read one clarification_lifecycle_outbox row (FOR UPDATE) for the caller's
    transaction. Does NOT mutate anything; a pure authoritative read under lock."""
    return _row(
        await conn.fetchrow(
            "SELECT * FROM clarification_lifecycle_outbox WHERE id=$1 FOR UPDATE",
            event_id,
        )
    )


async def resolve_event_scope(conn: asyncpg.Connection, event_id: str) -> dict[str, Any] | None:
    """Resolve the (task_id, project_id, production_effect) that authoritatively scope a dead
    outbox event, via its owning clarification -> task. Read-only; does not lock (the caller
    separately locks the outbox row itself under lock_outbox_event)."""
    return _row(
        await conn.fetchrow(
            """
            SELECT t.id AS task_id, t.project_id, t.production_effect, t.status AS task_status
            FROM clarification_lifecycle_outbox o
            JOIN operator_clarification_requests c ON c.id = o.clarification_id
            JOIN operator_tasks t ON t.id = c.task_id
            WHERE o.id = $1
            """,
            event_id,
        )
    )


# ---- replay_requests -----------------------------------------------------------------------------


async def insert_replay_request(
    conn: asyncpg.Connection,
    *,
    authorization_id: str,
    outbox_event_id: str,
    event_type: str,
    destination: str,
    team_id: str,
    project_id: str,
    resource_state_version: str,
    requested_by: str,
    idempotency_key: str,
) -> dict[str, Any]:
    """Insert a new replay request in state authorization_pending. The uq_rpr_active_per_event
    partial unique index rejects a second active request for the same event; a duplicate
    idempotency_key raises asyncpg.UniqueViolationError."""
    record = await conn.fetchrow(
        """
        INSERT INTO replay_requests
          (authorization_id, outbox_event_id, event_type, destination, team_id, project_id,
           resource_state_version, requested_by, idempotency_key)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
        RETURNING *
        """,
        authorization_id,
        outbox_event_id,
        event_type,
        destination,
        team_id,
        project_id,
        resource_state_version,
        requested_by,
        idempotency_key,
    )
    assert record is not None
    return dict(record)


async def get_replay_request_by_idempotency_key(
    conn: asyncpg.Connection, idempotency_key: str
) -> dict[str, Any] | None:
    return _row(
        await conn.fetchrow(
            "SELECT * FROM replay_requests WHERE idempotency_key=$1",
            idempotency_key,
        )
    )


async def get_replay_request(
    conn: asyncpg.Connection,
    replay_request_id: str,
    *,
    scope_team_id: str | None = None,
    scope_project_id: str | None = None,
) -> dict[str, Any] | None:
    """Read one replay request, scoped. A NULL/cross scope reads nothing (None)."""
    return _row(
        await conn.fetchrow(
            f"""
            SELECT * FROM replay_requests
            WHERE replay_request_id=$1 AND {_SCOPE.format(a="$2", b="$3")}
            """,
            replay_request_id,
            scope_team_id,
            scope_project_id,
        )
    )


async def lock_replay_request(
    conn: asyncpg.Connection,
    replay_request_id: str,
    *,
    scope_team_id: str | None = None,
    scope_project_id: str | None = None,
) -> dict[str, Any] | None:
    """Lock and read one replay request (FOR UPDATE), scoped."""
    return _row(
        await conn.fetchrow(
            f"""
            SELECT * FROM replay_requests
            WHERE replay_request_id=$1 AND {_SCOPE.format(a="$2", b="$3")}
            FOR UPDATE
            """,
            replay_request_id,
            scope_team_id,
            scope_project_id,
        )
    )


async def get_replay_request_internal(
    conn: asyncpg.Connection, replay_request_id: str
) -> dict[str, Any] | None:
    """Unscoped read for INTERNAL maintenance use only (expiry scan). Never actor-facing."""
    return _row(
        await conn.fetchrow(
            "SELECT * FROM replay_requests WHERE replay_request_id=$1", replay_request_id
        )
    )


async def transition_to_authorized(
    conn: asyncpg.Connection,
    replay_request_id: str,
    *,
    scope_team_id: str | None = None,
    scope_project_id: str | None = None,
) -> dict[str, Any] | None:
    """CAS authorization_pending -> authorized (sets authorized_at)."""
    return _row(
        await conn.fetchrow(
            f"""
            UPDATE replay_requests
            SET state='authorized', authorized_at=statement_timestamp(),
                updated_at=statement_timestamp()
            WHERE replay_request_id=$1 AND state='authorization_pending'
              AND {_SCOPE.format(a="$2", b="$3")}
            RETURNING *
            """,
            replay_request_id,
            scope_team_id,
            scope_project_id,
        )
    )


async def transition_to_rejected(
    conn: asyncpg.Connection,
    replay_request_id: str,
    *,
    reason_code: str,
    scope_team_id: str | None = None,
    scope_project_id: str | None = None,
) -> dict[str, Any] | None:
    """CAS authorization_pending -> rejected."""
    return _row(
        await conn.fetchrow(
            f"""
            UPDATE replay_requests
            SET state='rejected', rejected_at=statement_timestamp(),
                failure_reason_code=$2, updated_at=statement_timestamp()
            WHERE replay_request_id=$1 AND state='authorization_pending'
              AND {_SCOPE.format(a="$3", b="$4")}
            RETURNING *
            """,
            replay_request_id,
            reason_code,
            scope_team_id,
            scope_project_id,
        )
    )


async def transition_to_canceled(
    conn: asyncpg.Connection,
    replay_request_id: str,
    *,
    scope_team_id: str | None = None,
    scope_project_id: str | None = None,
) -> dict[str, Any] | None:
    """CAS authorization_pending -> canceled (an Operator may only cancel a still-pending request)."""
    return _row(
        await conn.fetchrow(
            f"""
            UPDATE replay_requests
            SET state='canceled', canceled_at=statement_timestamp(),
                updated_at=statement_timestamp()
            WHERE replay_request_id=$1 AND state='authorization_pending'
              AND {_SCOPE.format(a="$2", b="$3")}
            RETURNING *
            """,
            replay_request_id,
            scope_team_id,
            scope_project_id,
        )
    )


async def transition_to_executed(
    conn: asyncpg.Connection,
    replay_request_id: str,
    *,
    scope_team_id: str | None = None,
    scope_project_id: str | None = None,
) -> dict[str, Any] | None:
    """CAS authorized -> executed. Under concurrency EXACTLY ONE executor wins this CAS."""
    return _row(
        await conn.fetchrow(
            f"""
            UPDATE replay_requests
            SET state='executed', executed_at=statement_timestamp(),
                updated_at=statement_timestamp()
            WHERE replay_request_id=$1 AND state='authorized'
              AND {_SCOPE.format(a="$2", b="$3")}
            RETURNING *
            """,
            replay_request_id,
            scope_team_id,
            scope_project_id,
        )
    )


async def expire_due_replay_requests(
    conn: asyncpg.Connection, *, before: datetime, limit: int = 500
) -> int:
    """One-shot maintenance: mark still-pending/authorized requests whose bound authorization has
    expired as expired. NOT a scheduler/loop and NOT actor-facing (no scope filter). `before` is a
    DB-sourced timestamp supplied by the caller. Returns the number of rows expired."""
    tag = await conn.execute(
        """
        UPDATE replay_requests rr
        SET state='expired', expired_at=statement_timestamp(), updated_at=statement_timestamp()
        FROM resume_replay_authorizations a
        WHERE rr.authorization_id = a.authorization_id
          AND rr.state IN ('authorization_pending','authorized')
          AND a.expires_at <= $1
          AND rr.replay_request_id IN (
            SELECT replay_request_id FROM replay_requests
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


# ---- Rate limiting (server-side, DB-derived; bounded read-only COUNT queries) -------------------


async def acquire_actor_rate_limit_lock(
    conn: asyncpg.Connection, *, team_id: str, project_id: str, actor_id: str
) -> None:
    """Step 66C.4-BE3-R1 (finding L-1 closure): serialize the check-then-insert rate-limit sequence
    for one (team_id, project_id, actor_id) key within the CALLER's transaction. A PostgreSQL
    transaction-level advisory lock (`pg_advisory_xact_lock`, auto-released at commit/rollback, never
    held across a connection reuse) blocks a concurrent caller with the SAME key until this
    transaction ends, so `count_recent_requests_by_actor` + the eventual INSERT below can never race
    for that key -- a plain COUNT-then-INSERT with no lock can overshoot the cap under concurrency,
    which is exactly finding L-1. A hash collision between two DIFFERENT keys can only cause extra
    (harmless) serialization between unrelated actors/scopes; it can never loosen or merge their
    caps, since the actual COUNT query below is still exactly scoped by (team_id, project_id,
    actor_id). Must be called BEFORE any row lock in the caller (lock_outbox_event etc.) so every
    call path acquires locks in the same order and cannot deadlock against itself."""
    await conn.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended($1, 0))",
        f"be3-replay-actor-rate:{team_id}:{project_id}:{actor_id}",
    )


async def count_recent_requests_by_actor(
    conn: asyncpg.Connection, actor_id: str, *, team_id: str, project_id: str, window_hours: int
) -> int:
    """Count of replay requests BY THIS ACTOR, scoped to (team_id, project_id) (Step 66C.4-BE3-R1,
    finding L-1) so cross-team/cross-project rate-limit statistics are isolated and never share a
    budget. Counts every request row regardless of its later state (executed/canceled/rejected/
    expired all count) -- the cap protects against replay-request STORMS, not just successful
    replays, and an idempotent retry never adds a second row (uq_rpr_idempotency_key), so it is never
    double-counted. Call only while holding acquire_actor_rate_limit_lock for the same key."""
    return await conn.fetchval(
        "SELECT count(*) FROM replay_requests "
        "WHERE requested_by=$1 AND team_id=$2::uuid AND project_id=$3::uuid "
        "AND requested_at >= statement_timestamp() - ($4 || ' hours')::interval",
        actor_id,
        team_id,
        project_id,
        str(window_hours),
    )


async def count_successful_replays_for_event(
    conn: asyncpg.Connection, outbox_event_id: str, *, window_hours: int
) -> int:
    return await conn.fetchval(
        "SELECT count(*) FROM replay_requests "
        "WHERE outbox_event_id=$1 AND state='executed' "
        "AND executed_at >= statement_timestamp() - ($2 || ' hours')::interval",
        outbox_event_id,
        str(window_hours),
    )


# ---- Transaction-aware internal replay_dead adapter (Step 66C.4-BE3-C) --------------------------


async def replay_dead_row(
    conn: asyncpg.Connection,
    event_id: str,
    *,
    expected_resource_state_version: str,
) -> dict[str, Any] | None:
    """Transaction-aware replay: dead -> pending, state-version-guarded, inside the CALLER's
    transaction (never begins/commits/rolls back anything itself -- unlike
    ClarificationOutboxRelay.replay_dead, which always owns its own transaction and therefore
    cannot compose atomically with an authorization consume in the same unit of work).

    Preserves event_id, idempotency_key, event_type, payload, created_at. Does NOT reset attempts
    (plan_replay_state, same semantics as the existing relay foundation): a manual replay is one
    additional requeue opportunity, not a fresh five-attempt budget. Guarded by BOTH status='dead'
    AND the caller-supplied resource_state_version (dead_at:attempts snapshot) still matching the
    row's CURRENT dead_at/attempts -- a stale snapshot (the row died again since the snapshot was
    taken) fails the CAS and returns None with NO mutation.
    """
    row = await conn.fetchrow(
        "SELECT attempts, dead_at FROM clarification_lifecycle_outbox "
        "WHERE id=$1 AND status='dead' FOR UPDATE",
        event_id,
    )
    if row is None:
        return None
    current_version = dead_episode_state_version(dead_at=row["dead_at"], attempts=row["attempts"])
    if current_version != expected_resource_state_version:
        return None
    plan = plan_replay_state(attempts=int(row["attempts"]))
    return _row(
        await conn.fetchrow(
            """
            UPDATE clarification_lifecycle_outbox
            SET status='pending', attempts=$2, available_at=statement_timestamp(),
                dead_at=NULL, last_error=NULL
            WHERE id=$1
            RETURNING *
            """,
            event_id,
            plan["attempts"],
        )
    )
