"""Stage 40 -- incident_postmortems persistence."""

from __future__ import annotations

import json
import os
from typing import Any

import asyncpg

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"

STATUS_DRAFT = "draft"
STATUS_IN_REVIEW = "in_review"
STATUS_COMPLETED = "completed"
STATUS_CANCELLED = "cancelled"


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _row_to_dict(row: asyncpg.Record) -> dict[str, Any]:
    return {
        "postmortem_id": str(row["postmortem_id"]),
        "incident_id": str(row["incident_id"]),
        "status": row["status"],
        "summary": row["summary"],
        "root_cause": row["root_cause"],
        "impact": row["impact"],
        "timeline": list(row["timeline"] or []),
        "corrective_actions": list(row["corrective_actions"] or []),
        "owner": row["owner"],
        "due_at": _iso(row["due_at"]),
        "completed_at": _iso(row["completed_at"]),
        "document_path": row["document_path"],
        "created_at": _iso(row["created_at"]),
        "updated_at": _iso(row["updated_at"]),
        "metadata": dict(row["metadata"] or {}),
    }


class PostmortemStore:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.database_url, timeout=5)

    async def create_postmortem(
        self,
        *,
        incident_id: str,
        summary: str | None = None,
        owner: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO incident_postmortems
                  (incident_id, status, summary, owner, metadata)
                VALUES ($1::uuid, 'draft', $2, $3, $4::jsonb)
                RETURNING *
                """,
                incident_id,
                summary,
                owner,
                json.dumps(metadata or {}),
            )
        finally:
            await conn.close()
        return _row_to_dict(row)

    async def get_postmortem(self, postmortem_id: str) -> dict[str, Any] | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT * FROM incident_postmortems WHERE postmortem_id = $1::uuid",
                postmortem_id,
            )
        except (asyncpg.PostgresError, ValueError):
            row = None
        finally:
            await conn.close()
        return _row_to_dict(row) if row else None

    async def get_by_incident(self, incident_id: str) -> dict[str, Any] | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT * FROM incident_postmortems WHERE incident_id = $1::uuid ORDER BY created_at DESC LIMIT 1",
                incident_id,
            )
        except (asyncpg.PostgresError, ValueError):
            row = None
        finally:
            await conn.close()
        return _row_to_dict(row) if row else None

    async def list_postmortems(self, limit: int = 100) -> list[dict[str, Any]]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT * FROM incident_postmortems ORDER BY created_at DESC LIMIT $1",
                limit,
            )
        finally:
            await conn.close()
        return [_row_to_dict(r) for r in rows]

    async def count_required(self) -> int:
        """Count incident_records with postmortem_required=true and no completed postmortem."""
        conn = await self._connect()
        try:
            val = await conn.fetchval("""
                SELECT count(*) FROM incident_records ir
                WHERE  ir.postmortem_required = true
                  AND  NOT EXISTS (
                    SELECT 1 FROM incident_postmortems pm
                    WHERE pm.incident_id = ir.id
                      AND pm.status = 'completed'
                  )
                """)
        finally:
            await conn.close()
        return int(val or 0)


__all__ = [
    "PostmortemStore",
    "STATUS_DRAFT",
    "STATUS_IN_REVIEW",
    "STATUS_COMPLETED",
    "STATUS_CANCELLED",
]
