import json
import os
from typing import Any

import asyncpg

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"

_COLUMNS = (
    "task_id, stage, request, state, approval_required, "
    "approval_status, risk_level, execution_result, created_at, updated_at"
)


def _decode_json(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return value
    return value


def _row_to_dict(row: asyncpg.Record) -> dict:
    return {
        "task_id": row["task_id"],
        "stage": row["stage"],
        "request": _decode_json(row["request"]),
        "state": _decode_json(row["state"]),
        "approval_required": row["approval_required"],
        "approval_status": row["approval_status"],
        "risk_level": row["risk_level"],
        "execution_result": _decode_json(row["execution_result"]),
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


class WorkflowStore:
    """Persists LangGraph workflow state to the PostgreSQL workflow_states table.

    One row per workflow, keyed by task_id. The full LangGraph state dict is
    stored in the ``state`` JSONB column; the governance fields are also mirrored
    into dedicated columns so workflows can be listed and filtered.
    """

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.database_url, timeout=5)

    async def create_workflow_state(
        self, task_id: str, request: dict, stage: str = "intake"
    ) -> dict:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO workflow_states (task_id, stage, phase, request, state) "
                "VALUES ($1, $2, $2, $3::jsonb, $4::jsonb) "
                "ON CONFLICT (task_id) DO UPDATE SET "
                "stage = EXCLUDED.stage, phase = EXCLUDED.phase, "
                "request = EXCLUDED.request, state = EXCLUDED.state, updated_at = now() "
                f"RETURNING {_COLUMNS}",
                task_id,
                stage,
                json.dumps(request),
                json.dumps({}),
            )
        finally:
            await conn.close()
        return _row_to_dict(row)

    async def update_workflow_state(
        self,
        task_id: str,
        *,
        stage: str,
        state: dict,
        approval_required: bool,
        approval_status: str,
        risk_level: str,
        execution_result: dict,
    ) -> dict | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "UPDATE workflow_states SET "
                "stage = $2, phase = $2, state = $3::jsonb, approval_required = $4, "
                "approval_status = $5, risk_level = $6, execution_result = $7::jsonb, "
                "updated_at = now() WHERE task_id = $1 "
                f"RETURNING {_COLUMNS}",
                task_id,
                stage,
                json.dumps(state),
                approval_required,
                approval_status,
                risk_level,
                json.dumps(execution_result),
            )
        finally:
            await conn.close()
        return _row_to_dict(row) if row else None

    async def get_workflow_state(self, task_id: str) -> dict | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                f"SELECT {_COLUMNS} FROM workflow_states WHERE task_id = $1", task_id
            )
        finally:
            await conn.close()
        return _row_to_dict(row) if row else None

    async def list_workflows(self, status: str | None = None) -> list[dict]:
        conn = await self._connect()
        try:
            if status is None:
                rows = await conn.fetch(
                    f"SELECT {_COLUMNS} FROM workflow_states ORDER BY updated_at DESC"
                )
            else:
                rows = await conn.fetch(
                    f"SELECT {_COLUMNS} FROM workflow_states "
                    "WHERE stage = $1 OR approval_status = $1 ORDER BY updated_at DESC",
                    status,
                )
        finally:
            await conn.close()
        return [_row_to_dict(row) for row in rows]

    async def append_artifact(self, task_id: str, artifact: dict) -> dict | None:
        return await self._append_json_array(task_id, "artifacts", artifact)

    async def append_audit_ref(self, task_id: str, ref: str) -> dict | None:
        return await self._append_json_array(task_id, "audit_refs", ref)

    async def _append_json_array(self, task_id: str, key: str, value: Any) -> dict | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "UPDATE workflow_states SET "
                f"state = jsonb_set(state, '{{{key}}}', "
                f"COALESCE(state->'{key}', '[]'::jsonb) || $2::jsonb, true), "
                "updated_at = now() WHERE task_id = $1 "
                f"RETURNING {_COLUMNS}",
                task_id,
                json.dumps([value]),
            )
        finally:
            await conn.close()
        return _row_to_dict(row) if row else None
