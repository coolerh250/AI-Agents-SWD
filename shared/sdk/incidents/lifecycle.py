"""Stage 40 -- incident_lifecycle_events persistence."""

from __future__ import annotations

import json
import os
from typing import Any

import asyncpg

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"

EVENT_INCIDENT_CREATED = "incident_created"
EVENT_INCIDENT_ACKNOWLEDGED = "incident_acknowledged"
EVENT_INCIDENT_ESCALATED = "incident_escalated"
EVENT_INCIDENT_RESOLVED = "incident_resolved"
EVENT_INCIDENT_CLOSED = "incident_closed"
EVENT_INCIDENT_REOPENED = "incident_reopened"
EVENT_INCIDENT_POSTMORTEM_REQUIRED = "incident_postmortem_required"
EVENT_INCIDENT_POSTMORTEM_COMPLETED = "incident_postmortem_completed"
EVENT_INCIDENT_LINKED_TO_ALERT = "incident_linked_to_alert"
EVENT_INCIDENT_RUNBOOK_ATTACHED = "incident_runbook_attached"

ALL_LIFECYCLE_EVENTS = (
    EVENT_INCIDENT_CREATED,
    EVENT_INCIDENT_ACKNOWLEDGED,
    EVENT_INCIDENT_ESCALATED,
    EVENT_INCIDENT_RESOLVED,
    EVENT_INCIDENT_CLOSED,
    EVENT_INCIDENT_REOPENED,
    EVENT_INCIDENT_POSTMORTEM_REQUIRED,
    EVENT_INCIDENT_POSTMORTEM_COMPLETED,
    EVENT_INCIDENT_LINKED_TO_ALERT,
    EVENT_INCIDENT_RUNBOOK_ATTACHED,
)


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _row_to_dict(row: asyncpg.Record) -> dict[str, Any]:
    return {
        "lifecycle_event_id": str(row["lifecycle_event_id"]),
        "incident_id": str(row["incident_id"]),
        "event_type": row["event_type"],
        "previous_status": row["previous_status"],
        "new_status": row["new_status"],
        "actor_type": row["actor_type"],
        "actor_id": row["actor_id"],
        "reason": row["reason"],
        "created_at": _iso(row["created_at"]),
        "metadata": dict(row["metadata"] or {}),
    }


class LifecycleStore:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.database_url, timeout=5)

    async def record_event(
        self,
        *,
        incident_id: str,
        event_type: str,
        previous_status: str | None = None,
        new_status: str | None = None,
        actor_type: str = "operator",
        actor_id: str | None = None,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO incident_lifecycle_events
                  (incident_id, event_type, previous_status, new_status,
                   actor_type, actor_id, reason, metadata)
                VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8::jsonb)
                RETURNING *
                """,
                incident_id,
                event_type,
                previous_status,
                new_status,
                actor_type,
                actor_id,
                reason,
                json.dumps(metadata or {}),
            )
        finally:
            await conn.close()
        return _row_to_dict(row)

    async def list_events(self, incident_id: str) -> list[dict[str, Any]]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                """
                SELECT * FROM incident_lifecycle_events
                WHERE  incident_id = $1::uuid
                ORDER  BY created_at ASC
                """,
                incident_id,
            )
        except (asyncpg.PostgresError, ValueError):
            rows = []
        finally:
            await conn.close()
        return [_row_to_dict(r) for r in rows]


__all__ = [
    "LifecycleStore",
    "EVENT_INCIDENT_CREATED",
    "EVENT_INCIDENT_ACKNOWLEDGED",
    "EVENT_INCIDENT_ESCALATED",
    "EVENT_INCIDENT_RESOLVED",
    "EVENT_INCIDENT_CLOSED",
    "EVENT_INCIDENT_REOPENED",
    "EVENT_INCIDENT_POSTMORTEM_REQUIRED",
    "EVENT_INCIDENT_POSTMORTEM_COMPLETED",
    "EVENT_INCIDENT_LINKED_TO_ALERT",
    "EVENT_INCIDENT_RUNBOOK_ATTACHED",
]
