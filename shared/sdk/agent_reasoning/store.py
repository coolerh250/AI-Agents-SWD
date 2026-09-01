"""Step AT-M3.1 -- asyncpg store for reasoning invocations, their artifacts and their leases.

Persistence only: no provider call, no content-safety DECISION beyond the defense-in-depth
failure_reason sanitization below. Follows the existing store convention (connect per call,
``DATABASE_URL`` from the environment, plain dict rows) set by
``shared/sdk/agent_team/store.py``.

LIFECYCLE. Three operations, each of which is one atomic statement, because every guarantee here
has to hold across processes rather than inside one.

``try_begin_invocation`` atomically claims a correlation_id -- INSERT ... ON CONFLICT DO NOTHING,
status='started' -- BEFORE any provider is ever called. Exactly one concurrent caller gets
``owned=True`` and may invoke the provider; every other caller gets ``owned=False`` and the
EXISTING row's CURRENT state, with zero side effects. The claim also stamps an ownership lease.

``complete_invocation`` transitions a row from 'started' to a terminal status AND, on success,
writes the structured artifact -- in the SAME UPDATE, to the SAME row.

    That single sentence is the whole point of the AT-M3.4 rebaseline. This store used to record
    metadata only, so a row could commit status='succeeded' while the artifact existed nowhere but
    in the calling process's memory. If that process then died -- or merely rolled back its own
    downstream transaction -- the correlation was terminal, so no retry could ever re-invoke the
    provider, and replay had nothing to return. The work was stranded permanently, and AT-M3.4
    Validation 2 is where that came due. Writing the artifact in the terminal UPDATE removes the
    window rather than narrowing it: there is no ordering between "succeeded" and "the artifact",
    because they are one write. Migration 040's CHECK makes the bad state unrepresentable even for
    a caller that bypasses this module entirely.

``try_take_over_invocation`` recovers the OTHER way a call could strand. 037 deferred this
explicitly ("no lease/takeover recovery is implemented here"), which meant a worker that died
before its terminal UPDATE owned its correlation_id forever and every later caller was told
'in_progress' in perpetuity. Ownership is now bounded by a lease on the DATABASE clock, and an
expired lease is claimable by exactly one contender via compare-and-swap.

WHAT THIS HONESTLY GUARANTEES. Exactly one canonical artifact per correlation_id: the UNIQUE
constraint admits one row, the ``WHERE status='started'`` guard admits one terminalization, and
the artifact rides along with it. NOT exactly one provider call -- a process can always die after
the wire response and before the local commit, so a real external provider may be asked twice for
one correlation_id. That is at-least-once attempts with an exactly-once canonical result, and it
is stated plainly here because the alternative -- claiming a guarantee the architecture cannot
keep -- is how the stranding defect got written in the first place.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

import asyncpg

from shared.sdk.agent_reasoning.models import sanitize_failure_reason

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"

#: How long a claimed attempt owns its correlation_id before another worker may take it over.
#: Generous relative to a provider call and short relative to a human noticing a stuck discussion.
#: Measured on the DATABASE clock, never the application's -- an application clock is exactly what
#: a paused or skew-affected worker would use to extend its own ownership.
DEFAULT_LEASE_TTL_SECONDS = 120

#: How many times one correlation_id may be attempted before the invocation fails closed. Bounded
#: so a worker that reliably dies mid-call cannot produce an unbounded series of provider attempts.
#: Takeover is caller-driven -- nothing here polls, retries in the background, or runs on a timer.
DEFAULT_MAX_ATTEMPTS = 3

_COLUMNS = """
    invocation_id, project_id, thread_id, requested_by_principal_id, reasoning_verb,
    requested_provider_name, provider_mode, model_name, round_number, status,
    failure_category, failure_reason, artifact_type, artifact, attempt, attempt_token,
    lease_expires_at, outcome_ref, input_tokens, output_tokens,
    estimated_cost_usd, latency_ms, correlation_id, audit_ref, started_at, completed_at,
    created_at
"""


def _uuid_or_none(value: Any) -> uuid.UUID | None:
    if value is None:
        return None
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _decoded(row: asyncpg.Record | None) -> dict[str, Any] | None:
    """asyncpg returns JSONB as text unless a codec is registered; decode the one JSON column."""
    if row is None:
        return None
    data = dict(row)
    value = data.get("artifact")
    if isinstance(value, str):
        data["artifact"] = json.loads(value)
    return data


class ReasoningInvocationStore:
    def __init__(
        self,
        database_url: str | None = None,
        *,
        lease_ttl_seconds: int = DEFAULT_LEASE_TTL_SECONDS,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
        self.lease_ttl_seconds = lease_ttl_seconds
        self.max_attempts = max_attempts

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.database_url, timeout=5)

    # --- lifecycle: execution ownership + terminal transition -------------------------------

    async def try_begin_invocation(self, data: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        """Atomically claim ``data["correlation_id"]``. Returns ``(owned, row)``.

        ``owned=True``: this call's INSERT won -- the caller now OWNS execution and may invoke
        the provider. ``row["attempt_token"]`` is the proof of ownership it must present to
        ``complete_invocation``.
        ``owned=False``: a row already existed for this correlation_id -- the caller MUST NOT
        invoke the provider on the strength of this call. ``row`` is that existing row's current
        state, fetched in the same call, whatever it is (started/succeeded/failed).

        The lease is stamped from ``now()`` evaluated by PostgreSQL, so every worker's notion of
        when this attempt expires comes from one clock.
        """
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                f"""
                INSERT INTO reasoning_invocations
                  (project_id, thread_id, requested_by_principal_id, reasoning_verb,
                   requested_provider_name, provider_mode, model_name, round_number, status,
                   correlation_id, started_at, attempt, attempt_token, lease_expires_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,'started',$9,$10,
                        1, $11, now() + make_interval(secs => $12::double precision))
                ON CONFLICT (correlation_id) DO NOTHING
                RETURNING {_COLUMNS}
                """,
                _uuid_or_none(data.get("project_id")),
                _uuid_or_none(data.get("thread_id")),
                _uuid_or_none(data.get("requested_by_principal_id")),
                data["reasoning_verb"],
                data["requested_provider_name"],
                data["provider_mode"],
                data.get("model_name"),
                data.get("round_number", 1),
                _uuid_or_none(data["correlation_id"]),
                data["started_at"],
                uuid.uuid4(),
                float(self.lease_ttl_seconds),
            )
            if row is not None:
                return True, _decoded(row)  # type: ignore[return-value]
            existing = await conn.fetchrow(
                f"SELECT {_COLUMNS} FROM reasoning_invocations WHERE correlation_id=$1",
                _uuid_or_none(data["correlation_id"]),
            )
            return False, _decoded(existing)  # type: ignore[return-value]
        finally:
            await conn.close()

    async def try_take_over_invocation(self, correlation_id: Any) -> dict[str, Any] | None:
        """Claim a 'started' invocation whose lease has expired. Returns the row when this caller
        won the takeover, ``None`` when it did not.

        One compare-and-swap decides it. Two contenders both see an expired lease; the UPDATE
        serialises them on the row, and the second one's ``lease_expires_at`` predicate is no
        longer true because the first already pushed it forward -- so exactly one takeover happens
        and ``attempt`` advances exactly once per genuine recovery.

        ``lease_expires_at IS NULL`` on a 'started' row means the row predates migration 040's
        lease contract. Treating it as expired -- rather than as owned forever, or rewriting it --
        is what lets a legacy stranded attempt finally make progress without anyone editing
        history to achieve it.

        Returns ``None`` for a terminal row, a live lease, or an exhausted attempt budget. Those
        are three different situations and the caller distinguishes them by re-reading the row,
        because inventing a fourth return value for each would push the branching in here for no
        gain.
        """
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                f"""
                UPDATE reasoning_invocations SET
                    attempt = attempt + 1,
                    attempt_token = $2,
                    started_at = now(),
                    lease_expires_at = now() + make_interval(secs => $3::double precision)
                WHERE correlation_id = $1
                  AND status = 'started'
                  AND (lease_expires_at IS NULL OR now() >= lease_expires_at)
                  AND attempt < $4
                RETURNING {_COLUMNS}
                """,
                _uuid_or_none(correlation_id),
                uuid.uuid4(),
                float(self.lease_ttl_seconds),
                self.max_attempts,
            )
            return _decoded(row)
        finally:
            await conn.close()

    async def complete_invocation(
        self, invocation_id: Any, *, attempt_token: Any, terminal: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Transition ``invocation_id`` from 'started' to a terminal status, carrying its artifact.

        Guarded on BOTH ``status='started'`` and ``attempt_token``. The status guard is what makes
        a terminal row unoverwritable. The token guard is what makes a ZOMBIE safe: a worker whose
        lease expired and was taken over can still be alive and still return from its provider
        call, and without the token it would terminalize a result that nobody is waiting for and
        that silently outranks the attempt actually in flight. With it, the zombie's UPDATE matches
        no row and it learns it lost.

        ``failure_reason`` is sanitized here too (defense-in-depth), not only by the service --
        mirrors ``TeamStore.post_message`` re-checking content safety rather than trusting the
        Pydantic layer alone, since a direct store caller bypasses that layer entirely.

        ``artifact`` must be the already-validated ``as_safe_dict()`` payload for a success and
        must be absent for a failure; migration 040's CHECK enforces the pairing regardless of
        what any caller passes.

        Returns the resulting row: newly-terminal when this caller's write won, or -- when it did
        not -- the row's CURRENT state instead. That is not an error: it means this caller's write
        did not win, not that nothing exists. The caller compares ``attempt_token`` to find out
        which happened.
        """
        safe_reason = sanitize_failure_reason(terminal.get("failure_reason"))
        artifact = terminal.get("artifact")
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                f"""
                UPDATE reasoning_invocations SET
                    status=$3, failure_category=$4, failure_reason=$5, latency_ms=$6,
                    audit_ref=$7, completed_at=$8, artifact_type=$9, artifact=$10::jsonb,
                    lease_expires_at=NULL
                WHERE invocation_id=$1 AND attempt_token=$2 AND status='started'
                RETURNING {_COLUMNS}
                """,
                _uuid_or_none(invocation_id),
                _uuid_or_none(attempt_token),
                terminal["status"],
                terminal.get("failure_category"),
                safe_reason,
                terminal.get("latency_ms"),
                terminal.get("audit_ref"),
                terminal["completed_at"],
                terminal.get("artifact_type"),
                json.dumps(artifact) if artifact is not None else None,
            )
            if row is not None:
                return _decoded(row)
            current = await conn.fetchrow(
                f"SELECT {_COLUMNS} FROM reasoning_invocations WHERE invocation_id=$1",
                _uuid_or_none(invocation_id),
            )
            return _decoded(current)
        finally:
            await conn.close()

    async def fail_exhausted_invocation(
        self, invocation_id: Any, *, terminal: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Terminalize a 'started' row whose attempt budget is spent, without owning its token.

        The one write in this module that is not token-guarded, and the reason is specific: the
        row's recorded owner is by definition gone -- its lease expired and no further takeover is
        permitted -- so requiring its token would mean nothing could ever end the attempt, and
        'started' forever is precisely the state migration 040 exists to remove. Still guarded on
        ``status='started'``, so it can never overwrite a terminal outcome, and it writes a
        failure, which carries no artifact and therefore cannot fabricate a result.
        """
        safe_reason = sanitize_failure_reason(terminal.get("failure_reason"))
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                f"""
                UPDATE reasoning_invocations SET
                    status='failed', failure_category=$2, failure_reason=$3, completed_at=$4,
                    lease_expires_at=NULL
                WHERE invocation_id=$1 AND status='started'
                  AND (lease_expires_at IS NULL OR now() >= lease_expires_at)
                RETURNING {_COLUMNS}
                """,
                _uuid_or_none(invocation_id),
                terminal.get("failure_category", "provider_unavailable"),
                safe_reason,
                terminal["completed_at"],
            )
            if row is not None:
                return _decoded(row)
            current = await conn.fetchrow(
                f"SELECT {_COLUMNS} FROM reasoning_invocations WHERE invocation_id=$1",
                _uuid_or_none(invocation_id),
            )
            return _decoded(current)
        finally:
            await conn.close()

    # --- read-only ---------------------------------------------------------------------------

    async def get_by_correlation_id(self, correlation_id: str) -> dict[str, Any] | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                f"SELECT {_COLUMNS} FROM reasoning_invocations WHERE correlation_id=$1",
                _uuid_or_none(correlation_id),
            )
            return _decoded(row)
        finally:
            await conn.close()

    async def list_for_project(self, project_id: str, limit: int = 100) -> list[dict[str, Any]]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                f"""
                SELECT {_COLUMNS} FROM reasoning_invocations
                WHERE project_id=$1 ORDER BY created_at DESC LIMIT $2
                """,
                _uuid_or_none(project_id),
                limit,
            )
            return [_decoded(row) for row in rows]  # type: ignore[misc]
        finally:
            await conn.close()


__all__ = [
    "DEFAULT_DATABASE_URL",
    "DEFAULT_LEASE_TTL_SECONDS",
    "DEFAULT_MAX_ATTEMPTS",
    "ReasoningInvocationStore",
]
