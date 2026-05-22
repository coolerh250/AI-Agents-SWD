import json
import os
from typing import Any

import asyncpg

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"

_COLUMNS = (
    "id, task_id, agent, status, started_at, "
    "completed_at, error, metadata, created_at, updated_at"
)


def _decode_json(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return value
    return value


def _iso(value: Any) -> Any:
    return value.isoformat() if value is not None else None


def _row_to_dict(row: asyncpg.Record) -> dict:
    return {
        "execution_id": str(row["id"]),
        "task_id": row["task_id"],
        "agent": row["agent"],
        "status": row["status"],
        "started_at": _iso(row["started_at"]),
        "completed_at": _iso(row["completed_at"]),
        "error": row["error"],
        "metadata": _decode_json(row["metadata"]),
        "created_at": _iso(row["created_at"]),
        "updated_at": _iso(row["updated_at"]),
    }


class AgentExecutionStore:
    """Persists agent execution records to the PostgreSQL agent_executions table.

    One row per message an agent processes: created with status ``started`` and
    moved to ``completed`` or ``failed`` when the agent finishes.
    """

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.database_url, timeout=5)

    async def create_execution(
        self, task_id: str, agent: str, metadata: dict | None = None
    ) -> dict:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO agent_executions "
                "(task_id, agent, agent_name, status, started_at, metadata) "
                "VALUES ($1, $2, $2, 'started', now(), $3::jsonb) "
                f"RETURNING {_COLUMNS}",
                task_id,
                agent,
                json.dumps(metadata or {}),
            )
        finally:
            await conn.close()
        return _row_to_dict(row)

    async def update_execution(
        self,
        execution_id: str,
        *,
        status: str | None = None,
        metadata: dict | None = None,
        error: str | None = None,
    ) -> dict | None:
        return await self._run_update(
            "UPDATE agent_executions SET "
            "status = COALESCE($2, status), "
            "metadata = COALESCE($3::jsonb, metadata), "
            "error = COALESCE($4, error), updated_at = now() "
            "WHERE id = $1::uuid "
            f"RETURNING {_COLUMNS}",
            execution_id,
            status,
            json.dumps(metadata) if metadata is not None else None,
            error,
        )

    async def complete_execution(
        self, execution_id: str, metadata: dict | None = None
    ) -> dict | None:
        return await self._run_update(
            "UPDATE agent_executions SET "
            "status = 'completed', completed_at = now(), finished_at = now(), "
            "metadata = COALESCE($2::jsonb, metadata), updated_at = now() "
            "WHERE id = $1::uuid "
            f"RETURNING {_COLUMNS}",
            execution_id,
            json.dumps(metadata) if metadata is not None else None,
        )

    async def fail_execution(
        self, execution_id: str, error: str, metadata: dict | None = None
    ) -> dict | None:
        return await self._run_update(
            "UPDATE agent_executions SET "
            "status = 'failed', completed_at = now(), finished_at = now(), "
            "error = $2, metadata = COALESCE($3::jsonb, metadata), updated_at = now() "
            "WHERE id = $1::uuid "
            f"RETURNING {_COLUMNS}",
            execution_id,
            error,
            json.dumps(metadata) if metadata is not None else None,
        )

    async def _run_update(self, query: str, *args: Any) -> dict | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(query, *args)
        except (asyncpg.PostgresError, ValueError):
            row = None
        finally:
            await conn.close()
        return _row_to_dict(row) if row else None

    async def get_execution(self, execution_id: str) -> dict | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                f"SELECT {_COLUMNS} FROM agent_executions WHERE id = $1::uuid",
                execution_id,
            )
        except (asyncpg.PostgresError, ValueError):
            row = None
        finally:
            await conn.close()
        return _row_to_dict(row) if row else None

    async def list_executions(
        self,
        task_id: str | None = None,
        agent: str | None = None,
        status: str | None = None,
    ) -> list[dict]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                f"SELECT {_COLUMNS} FROM agent_executions "
                "WHERE ($1::text IS NULL OR task_id = $1) "
                "AND ($2::text IS NULL OR agent = $2) "
                "AND ($3::text IS NULL OR status = $3) "
                "ORDER BY created_at DESC",
                task_id,
                agent,
                status,
            )
        finally:
            await conn.close()
        return [_row_to_dict(row) for row in rows]
