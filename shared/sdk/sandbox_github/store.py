"""Step 59 -- asyncpg store for sandbox GitHub draft PR records.

Persists each draft-PR request (dry_run plan or live result) with its project /
work-item / dispatch / correlation linkage. A record is NOT a merge, NOT a review,
NOT a production approval -- it is a sandbox draft-PR request artifact only.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import asyncpg

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"

_COLS = (
    "id, project_id, project_key, work_item_id, work_item_key, dispatch_id, correlation_id, "
    "repository_key, branch_name, draft_pr_url, draft_pr_number, mode, status, audit_event_id, "
    "created_at"
)


class SandboxDraftPrStore:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.database_url, timeout=5)

    @staticmethod
    def _row(row: asyncpg.Record | None) -> dict[str, Any] | None:
        if row is None:
            return None
        d = dict(row)
        if d.get("id") is not None:
            d["id"] = str(d["id"])
        if d.get("project_id") is not None:
            d["project_id"] = str(d["project_id"])
        if d.get("work_item_id") is not None:
            d["work_item_id"] = str(d["work_item_id"])
        if d.get("created_at") is not None:
            d["created_at"] = d["created_at"].isoformat()
        return d

    async def create_request(
        self,
        *,
        project_id: str | None,
        project_key: str | None,
        work_item_id: str | None,
        work_item_key: str | None,
        dispatch_id: str | None,
        correlation_id: str,
        repository_key: str,
        branch_name: str | None,
        draft_pr_url: str | None,
        draft_pr_number: int | None,
        mode: str,
        status: str,
        audit_event_id: str | None,
    ) -> dict[str, Any]:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                f"""
                INSERT INTO sandbox_github_draft_prs
                  (project_id, project_key, work_item_id, work_item_key, dispatch_id,
                   correlation_id, repository_key, branch_name, draft_pr_url, draft_pr_number,
                   mode, status, audit_event_id)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
                RETURNING {_COLS}
                """,
                uuid.UUID(project_id) if project_id else None,
                project_key,
                uuid.UUID(work_item_id) if work_item_id else None,
                work_item_key,
                dispatch_id,
                correlation_id,
                repository_key,
                branch_name,
                draft_pr_url,
                draft_pr_number,
                mode,
                status,
                audit_event_id,
            )
            return self._row(row)  # type: ignore[return-value]
        finally:
            await conn.close()

    async def get_request(self, request_id: str) -> dict[str, Any] | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                f"SELECT {_COLS} FROM sandbox_github_draft_prs WHERE id=$1", uuid.UUID(request_id)
            )
            return self._row(row)
        finally:
            await conn.close()

    async def list_requests(self, limit: int = 100) -> list[dict[str, Any]]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                f"SELECT {_COLS} FROM sandbox_github_draft_prs ORDER BY created_at DESC LIMIT $1",
                int(limit),
            )
            return [self._row(r) for r in rows]  # type: ignore[misc]
        finally:
            await conn.close()

    async def count_created(self) -> int:
        conn = await self._connect()
        try:
            val = await conn.fetchval(
                "SELECT count(*) FROM sandbox_github_draft_prs WHERE status='created'"
            )
            return int(val or 0)
        finally:
            await conn.close()


__all__ = ["SandboxDraftPrStore"]
