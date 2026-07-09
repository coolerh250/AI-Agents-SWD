"""Step 66B.1 -- asyncpg store for the operator_tasks table.

No production action; production_effect defaults false and is never executed on --
it only forces a non-dispatchable status (see task_api.py).
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

import asyncpg

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"


class TaskStore:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.database_url, timeout=5)

    async def create_task(
        self,
        *,
        title: str,
        description: str | None,
        task_type: str,
        priority: str,
        created_by: str,
        owner: str | None,
        project_id: str | None,
        environment: str,
        production_effect: bool,
        requires_approval: bool,
        intake_planning_only: bool,
        status: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO operator_tasks
                  (title, description, task_type, priority, status, created_by, owner, project_id,
                   environment, production_effect, requires_approval, intake_planning_only, metadata)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13::jsonb)
                RETURNING *
                """,
                title,
                description,
                task_type,
                priority,
                status,
                created_by,
                owner,
                uuid.UUID(project_id) if project_id else None,
                environment,
                production_effect,
                requires_approval,
                intake_planning_only,
                json.dumps(metadata or {}),
            )
            return self._row(row)
        finally:
            await conn.close()

    async def get_task(self, task_id: str) -> dict[str, Any] | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT * FROM operator_tasks WHERE id=$1", uuid.UUID(task_id)
            )
            return self._row(row) if row else None
        finally:
            await conn.close()

    async def list_tasks(
        self,
        *,
        status: str | None = None,
        task_type: str | None = None,
        owner: str | None = None,
        created_by: str | None = None,
        priority: str | None = None,
        environment: str | None = None,
    ) -> list[dict[str, Any]]:
        conn = await self._connect()
        try:
            clauses: list[str] = []
            params: list[Any] = []
            for col, val in (
                ("status", status),
                ("task_type", task_type),
                ("owner", owner),
                ("created_by", created_by),
                ("priority", priority),
                ("environment", environment),
            ):
                if val is not None:
                    params.append(val)
                    clauses.append(f"{col}=${len(params)}")
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            rows = await conn.fetch(
                f"SELECT * FROM operator_tasks {where} ORDER BY created_at DESC",  # noqa: S608
                *params,
            )
            return [self._row(r) for r in rows]
        finally:
            await conn.close()

    async def update_status(self, task_id: str, new_status: str) -> dict[str, Any]:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "UPDATE operator_tasks SET status=$2, updated_at=now() WHERE id=$1 RETURNING *",
                uuid.UUID(task_id),
                new_status,
            )
            return self._row(row)
        finally:
            await conn.close()

    @staticmethod
    def _row(row: asyncpg.Record) -> dict[str, Any]:
        d = dict(row)
        for key in ("id", "project_id", "correlation_id"):
            if d.get(key) is not None:
                d[key] = str(d[key])
        if isinstance(d.get("metadata"), str):
            d["metadata"] = json.loads(d["metadata"])
        for key in ("created_at", "updated_at"):
            if d.get(key) is not None:
                d[key] = d[key].isoformat()
        return d


__all__ = ["TaskStore", "DEFAULT_DATABASE_URL"]
