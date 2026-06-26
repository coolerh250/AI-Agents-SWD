"""Step 57 -- asyncpg store for work items, dispatches, and events.

Extends the existing project_work_items table (017) with the delivery lifecycle and
adds dispatch / event rows. No production action; production_effect defaults false.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

import asyncpg

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"


class WorkItemStore:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.database_url, timeout=5)

    async def create_work_item(
        self,
        *,
        project_id: str,
        title: str,
        description: str | None,
        work_type: str,
        priority: str,
        item_source: str | None,
        requested_by: str | None,
        requires_human_approval: bool,
        production_effect: bool,
    ) -> dict[str, Any]:
        conn = await self._connect()
        try:
            count = await conn.fetchval(
                "SELECT count(*) FROM project_work_items WHERE project_id=$1", uuid.UUID(project_id)
            )
            work_item_key = f"WI-{int(count) + 1:04d}"
            row = await conn.fetchrow(
                """
                INSERT INTO project_work_items
                  (project_id, work_item_key, title, description, work_type, priority,
                   item_source, requested_by, requires_human_approval, production_effect,
                   lifecycle_state, status)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,'created','pending')
                RETURNING id, project_id, work_item_key, title, description, work_type,
                          priority, lifecycle_state, assigned_agent, requires_human_approval,
                          production_effect, delivery_package_id, created_at
                """,
                uuid.UUID(project_id),
                work_item_key,
                title,
                description,
                work_type,
                priority,
                item_source,
                requested_by,
                requires_human_approval,
                production_effect,
            )
            return self._wi_row(row)
        finally:
            await conn.close()

    async def get_work_item(self, work_item_id: str) -> dict[str, Any] | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT * FROM project_work_items WHERE id=$1", uuid.UUID(work_item_id)
            )
            return self._wi_row(row) if row else None
        finally:
            await conn.close()

    async def list_work_items(self, project_id: str) -> list[dict[str, Any]]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT * FROM project_work_items WHERE project_id=$1 ORDER BY created_at",
                uuid.UUID(project_id),
            )
            return [self._wi_row(r) for r in rows]
        finally:
            await conn.close()

    async def set_lifecycle_state(self, work_item_id: str, new_state: str) -> None:
        conn = await self._connect()
        try:
            completed = ", completed_at = now()" if new_state == "completed" else ""
            await conn.execute(
                f"UPDATE project_work_items SET lifecycle_state=$2, updated_at=now(){completed} "
                "WHERE id=$1",
                uuid.UUID(work_item_id),
                new_state,
            )
        finally:
            await conn.close()

    async def set_assigned_agent(self, work_item_id: str, agent: str) -> None:
        conn = await self._connect()
        try:
            await conn.execute(
                "UPDATE project_work_items SET assigned_agent=$2, updated_at=now() WHERE id=$1",
                uuid.UUID(work_item_id),
                agent,
            )
        finally:
            await conn.close()

    async def create_dispatch(
        self,
        *,
        project_id: str,
        work_item_id: str,
        dispatch_key: str,
        target_agent: str,
        target_stream: str,
        correlation_id: str,
    ) -> dict[str, Any]:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO work_item_dispatches
                  (project_id, work_item_id, dispatch_key, target_agent, target_stream,
                   status, correlation_id, production_effect)
                VALUES ($1,$2,$3,$4,$5,'dispatched',$6,false)
                RETURNING id, project_id, work_item_id, dispatch_key, target_agent,
                          target_stream, status, attempt, correlation_id, production_effect,
                          created_at
                """,
                uuid.UUID(project_id),
                uuid.UUID(work_item_id),
                dispatch_key,
                target_agent,
                target_stream,
                correlation_id,
            )
            return self._dispatch_row(row)
        finally:
            await conn.close()

    async def list_dispatches(self, work_item_id: str) -> list[dict[str, Any]]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT * FROM work_item_dispatches WHERE work_item_id=$1 ORDER BY created_at",
                uuid.UUID(work_item_id),
            )
            return [self._dispatch_row(r) for r in rows]
        finally:
            await conn.close()

    async def record_event(
        self,
        *,
        project_id: str,
        work_item_id: str,
        event_type: str,
        from_state: str | None,
        to_state: str | None,
        actor: str | None,
        role: str | None,
        reason: str | None,
        correlation_id: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        conn = await self._connect()
        try:
            await conn.execute(
                """
                INSERT INTO work_item_events
                  (project_id, work_item_id, event_type, from_state, to_state, actor, role,
                   reason, correlation_id, metadata)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::jsonb)
                """,
                uuid.UUID(project_id),
                uuid.UUID(work_item_id),
                event_type,
                from_state,
                to_state,
                actor,
                role,
                reason,
                correlation_id,
                json.dumps(metadata or {}),
            )
        finally:
            await conn.close()

    async def list_events(self, work_item_id: str) -> list[dict[str, Any]]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT * FROM work_item_events WHERE work_item_id=$1 ORDER BY created_at",
                uuid.UUID(work_item_id),
            )
            return [self._event_row(r) for r in rows]
        finally:
            await conn.close()

    async def link_delivery_package(
        self,
        *,
        project_id: str,
        work_item_id: str,
        delivery_package_id: str | None,
        dispatch_id: str | None,
    ) -> dict[str, Any]:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO project_delivery_packages
                  (project_id, work_item_id, dispatch_id, delivery_package_id,
                   acceptance_status, production_ready)
                VALUES ($1,$2,$3,$4,'pending',false)
                RETURNING id, project_id, work_item_id, delivery_package_id, acceptance_status,
                          production_ready, created_at
                """,
                uuid.UUID(project_id),
                uuid.UUID(work_item_id),
                uuid.UUID(dispatch_id) if dispatch_id else None,
                uuid.UUID(delivery_package_id) if delivery_package_id else None,
            )
            if delivery_package_id:
                await conn.execute(
                    "UPDATE project_work_items SET delivery_package_id=$2 WHERE id=$1",
                    uuid.UUID(work_item_id),
                    uuid.UUID(delivery_package_id),
                )
            return {
                "id": str(row["id"]),
                "project_id": str(row["project_id"]),
                "work_item_id": str(row["work_item_id"]),
                "delivery_package_id": (
                    str(row["delivery_package_id"]) if row["delivery_package_id"] else None
                ),
                "acceptance_status": row["acceptance_status"],
                "production_ready": row["production_ready"],
            }
        finally:
            await conn.close()

    @staticmethod
    def _wi_row(r: asyncpg.Record) -> dict[str, Any]:
        return {
            "id": str(r["id"]),
            "project_id": str(r["project_id"]),
            "work_item_key": r["work_item_key"],
            "title": r["title"],
            "description": r["description"],
            "work_type": r["work_type"],
            "priority": r["priority"],
            "lifecycle_state": r["lifecycle_state"],
            "assigned_agent": r["assigned_agent"],
            "requires_human_approval": r["requires_human_approval"],
            "production_effect": r["production_effect"],
            "delivery_package_id": (
                str(r["delivery_package_id"]) if r["delivery_package_id"] else None
            ),
        }

    @staticmethod
    def _dispatch_row(r: asyncpg.Record) -> dict[str, Any]:
        return {
            "id": str(r["id"]),
            "project_id": str(r["project_id"]),
            "work_item_id": str(r["work_item_id"]),
            "dispatch_key": r["dispatch_key"],
            "target_agent": r["target_agent"],
            "target_stream": r["target_stream"],
            "status": r["status"],
            "attempt": r["attempt"],
            "correlation_id": r["correlation_id"],
            "production_effect": r["production_effect"],
        }

    @staticmethod
    def _event_row(r: asyncpg.Record) -> dict[str, Any]:
        meta = r["metadata"]
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except (ValueError, TypeError):
                meta = {}
        return {
            "id": str(r["id"]),
            "project_id": str(r["project_id"]),
            "work_item_id": str(r["work_item_id"]),
            "event_type": r["event_type"],
            "from_state": r["from_state"],
            "to_state": r["to_state"],
            "actor": r["actor"],
            "role": r["role"],
            "reason": r["reason"],
            "correlation_id": r["correlation_id"],
            "metadata": meta,
        }
