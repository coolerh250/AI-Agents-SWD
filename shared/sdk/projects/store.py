"""Step 57 -- asyncpg store for the project registry + delivery-state rollup.

Extends the existing projects table (017) with registry semantics. No production
action; production_allowed / production_ready default false.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import asyncpg

from shared.sdk.projects.registry import project_key_from_name

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"


def compute_delivery_state(work_items: list[dict[str, Any]]) -> str:
    """Deterministic project delivery-state rollup from work-item lifecycle states."""
    if not work_items:
        return "not_started"
    states = [w.get("lifecycle_state") for w in work_items]
    if "blocked" in states:
        return "blocked"
    if "waiting_approval" in states:
        return "operator_review"
    in_progress = [
        w for w in work_items if w.get("lifecycle_state") in ("dispatched", "in_progress")
    ]

    def any_type(types: set[str]) -> bool:
        return any((w.get("work_type") or "") in types for w in in_progress)

    if any_type({"qa", "verification"}):
        return "qa_active"
    if any_type({"delivery_package"}):
        return "packaging_active"
    if any_type({"implementation", "backend", "frontend"}):
        return "implementation_active"
    if any_type({"planning", "architecture"}):
        return "planning_active"
    if any_type({"requirement"}):
        return "intake_active"
    terminal = {"completed", "cancelled", "archived"}
    if all(s in terminal for s in states) and "completed" in states:
        return "completed_nonproduction"
    return "not_started"


class ProjectStore:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.database_url, timeout=5)

    async def create_project(
        self, *, name: str, description: str | None, environment_scope: str, requester: str | None
    ) -> dict[str, Any]:
        conn = await self._connect()
        try:
            short = uuid.uuid4().hex[:6]
            key = project_key_from_name(name, suffix=short)
            row = await conn.fetchrow(
                """
                INSERT INTO projects
                  (title, summary, requester, request_source, project_key, environment_scope,
                   production_allowed, registry_status, status)
                VALUES ($1,$2,$3,'multi_project_api',$4,$5,false,'active','draft')
                RETURNING id, title, summary, project_key, environment_scope, production_allowed,
                          registry_status, created_at
                """,
                name,
                description,
                requester,
                key,
                environment_scope,
            )
            return self._row(row)
        finally:
            await conn.close()

    async def get_project(self, project_id: str) -> dict[str, Any] | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT id, title, summary, project_key, environment_scope, production_allowed, "
                "registry_status, created_at FROM projects WHERE id=$1",
                uuid.UUID(project_id),
            )
            return self._row(row) if row else None
        finally:
            await conn.close()

    async def list_projects(self) -> list[dict[str, Any]]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT id, title, summary, project_key, environment_scope, production_allowed, "
                "registry_status, created_at FROM projects WHERE project_key IS NOT NULL "
                "ORDER BY created_at DESC"
            )
            return [self._row(r) for r in rows]
        finally:
            await conn.close()

    async def upsert_delivery_state(self, project_id: str, delivery_state: str) -> dict[str, Any]:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO project_delivery_states (project_id, delivery_state, production_ready)
                VALUES ($1,$2,false)
                ON CONFLICT (project_id) DO UPDATE
                  SET delivery_state=EXCLUDED.delivery_state, updated_at=now()
                RETURNING project_id, delivery_state, production_ready
                """,
                uuid.UUID(project_id),
                delivery_state,
            )
            return {
                "project_id": str(row["project_id"]),
                "delivery_state": row["delivery_state"],
                "production_ready": row["production_ready"],
            }
        finally:
            await conn.close()

    @staticmethod
    def _row(r: asyncpg.Record) -> dict[str, Any]:
        return {
            "project_id": str(r["id"]),
            "project_key": r["project_key"],
            "name": r["title"],
            "description": r["summary"],
            "registry_status": r["registry_status"],
            "environment_scope": r["environment_scope"],
            "production_allowed": r["production_allowed"],
        }
