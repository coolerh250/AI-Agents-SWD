"""Step AT-M3.1 -- asyncpg store for reasoning-invocation metadata.

Persistence only: no audit, no provider call, no content-safety decision. Follows the existing
store convention (connect per call, ``DATABASE_URL`` from the environment, plain dict rows) set by
``shared/sdk/agent_team/store.py``.

Idempotency lives here: ``correlation_id`` is UNIQUE at the schema layer (migration 037), and
``record_invocation`` inserts with ``ON CONFLICT ... DO NOTHING`` and re-fetches on conflict, so a
replayed call with the same ``correlation_id`` always resolves to the SAME row rather than a
second one -- the row is the authoritative outcome; it is never persisted twice.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import asyncpg

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

    async def record_invocation(self, data: dict[str, Any]) -> dict[str, Any]:
        """Insert one invocation row, or return the existing one for a replayed correlation_id."""
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                f"""
                INSERT INTO reasoning_invocations
                  (project_id, thread_id, requested_by_principal_id, reasoning_verb,
                   requested_provider_name, provider_mode, model_name, round_number, status,
                   failure_category, failure_reason, outcome_ref, input_tokens, output_tokens,
                   estimated_cost_usd, latency_ms, correlation_id, audit_ref, started_at,
                   completed_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20)
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
                data["status"],
                data.get("failure_category"),
                data.get("failure_reason"),
                data.get("outcome_ref"),
                data.get("input_tokens"),
                data.get("output_tokens"),
                data.get("estimated_cost_usd"),
                data.get("latency_ms"),
                _uuid_or_none(data["correlation_id"]),
                data.get("audit_ref"),
                data.get("started_at"),
                data.get("completed_at"),
            )
            if row is None:
                # A row with this correlation_id already existed -- the conflict IS the answer.
                row = await conn.fetchrow(
                    f"SELECT {_COLUMNS} FROM reasoning_invocations WHERE correlation_id=$1",
                    _uuid_or_none(data["correlation_id"]),
                )
            return dict(row)
        finally:
            await conn.close()

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
