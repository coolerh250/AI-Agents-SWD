"""Step AT-M3.1 -- asyncpg store for reasoning-invocation metadata.

Persistence only: no provider call, no content-safety DECISION beyond the defense-in-depth
failure_reason sanitization below. Follows the existing store convention (connect per call,
``DATABASE_URL`` from the environment, plain dict rows) set by
``shared/sdk/agent_team/store.py``.

LIFECYCLE (AT-M3.1-REMEDIATION-1, Validation 1 blocker 1+2): two operations replace what used to be
a single ``record_invocation`` call made only after the provider had already run.

``try_begin_invocation`` atomically claims a correlation_id -- INSERT ... ON CONFLICT DO NOTHING,
status='started' -- BEFORE any provider is ever called. Exactly one concurrent caller gets
``owned=True`` and may invoke the provider; every other caller, whether racing or arriving after
the winner's terminal update, gets ``owned=False`` and the EXISTING row's CURRENT state (started,
succeeded, or failed) with zero side effects -- it never invokes the provider.

``complete_invocation`` transitions a row from 'started' to a terminal status via
``UPDATE ... WHERE status='started'``, so a terminal row can never be overwritten. If the terminal
write itself fails (a dropped connection, for example), the 'started' row inserted before the
provider ran is already durable -- it is not lost, only left non-terminal, which is the explicit,
accepted state for this slice (no lease/takeover recovery is implemented here).
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import asyncpg

from shared.sdk.agent_reasoning.models import sanitize_failure_reason

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"

_COLUMNS = """
    invocation_id, project_id, thread_id, requested_by_principal_id, reasoning_verb,
    requested_provider_name, provider_mode, model_name, round_number, status,
    failure_category, failure_reason, outcome_ref, input_tokens, output_tokens,
    estimated_cost_usd, latency_ms, correlation_id, audit_ref, started_at, completed_at,
    created_at
"""


def _uuid_or_none(value: Any) -> uuid.UUID | None:
    if value is None:
        return None
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


class ReasoningInvocationStore:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.database_url, timeout=5)

    # --- lifecycle: execution ownership + terminal transition -------------------------------

    async def try_begin_invocation(self, data: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        """Atomically claim ``data["correlation_id"]``. Returns ``(owned, row)``.

        ``owned=True``: this call's INSERT won -- the caller now OWNS execution and may invoke
        the provider.
        ``owned=False``: a row already existed for this correlation_id -- the caller MUST NOT
        invoke the provider. ``row`` is that existing row's current state, fetched in the same
        call, whatever it is (started/succeeded/failed).
        """
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                f"""
                INSERT INTO reasoning_invocations
                  (project_id, thread_id, requested_by_principal_id, reasoning_verb,
                   requested_provider_name, provider_mode, model_name, round_number, status,
                   correlation_id, started_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,'started',$9,$10)
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
            )
            if row is not None:
                return True, dict(row)
            existing = await conn.fetchrow(
                f"SELECT {_COLUMNS} FROM reasoning_invocations WHERE correlation_id=$1",
                _uuid_or_none(data["correlation_id"]),
            )
            return False, dict(existing)
        finally:
            await conn.close()

    async def complete_invocation(
        self, invocation_id: Any, *, terminal: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Transition ``invocation_id`` from 'started' to a terminal status. Owner-only call.

        ``failure_reason`` is sanitized here too (defense-in-depth), not only by the service --
        mirrors ``TeamStore.post_message`` re-checking content safety rather than trusting the
        Pydantic layer alone, since a direct store caller bypasses that layer entirely.

        Returns the resulting row: newly-terminal on success, or -- if the row had already left
        'started' before this call ran, so the UPDATE affected zero rows -- the row's CURRENT
        state instead. That is not an error: it means this caller's write did not win, not that
        nothing exists.
        """
        safe_reason = sanitize_failure_reason(terminal.get("failure_reason"))
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                f"""
                UPDATE reasoning_invocations SET
                    status=$2, failure_category=$3, failure_reason=$4, latency_ms=$5,
                    audit_ref=$6, completed_at=$7
                WHERE invocation_id=$1 AND status='started'
                RETURNING {_COLUMNS}
                """,
                _uuid_or_none(invocation_id),
                terminal["status"],
                terminal.get("failure_category"),
                safe_reason,
                terminal.get("latency_ms"),
                terminal.get("audit_ref"),
                terminal["completed_at"],
            )
            if row is not None:
                return dict(row)
            current = await conn.fetchrow(
                f"SELECT {_COLUMNS} FROM reasoning_invocations WHERE invocation_id=$1",
                _uuid_or_none(invocation_id),
            )
            return dict(current) if current else None
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
            return dict(row) if row else None
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
            return [dict(row) for row in rows]
        finally:
            await conn.close()


__all__ = ["DEFAULT_DATABASE_URL", "ReasoningInvocationStore"]
