import json
import os
from typing import Any

import asyncpg

from shared.sdk.incidents.models import (
    Incident,
    normalize_severity,
    normalize_status,
)
from shared.sdk.observability.tracing import start_span

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"

_COLUMNS = (
    "id, task_id, workflow_id, severity, normalized_severity, status, source, summary, "
    "details, postmortem_required, acknowledged_at, resolved_at, closed_at, created_at, updated_at"
)


def _decode_details(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
            return decoded if isinstance(decoded, dict) else {}
        except (ValueError, TypeError):
            return {}
    if isinstance(value, dict):
        return dict(value)
    return {}


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _row_to_incident(row: asyncpg.Record) -> Incident:
    return Incident(
        incident_id=str(row["id"]),
        task_id=row["task_id"],
        workflow_id=row["workflow_id"],
        severity=str(row["severity"]),
        normalized_severity=row["normalized_severity"],
        status=str(row["status"]),
        source=str(row["source"]),
        summary=str(row["summary"]),
        details=_decode_details(row["details"]),
        postmortem_required=(
            bool(row["postmortem_required"]) if row["postmortem_required"] is not None else False
        ),
        acknowledged_at=_iso(row["acknowledged_at"]),
        resolved_at=_iso(row["resolved_at"]),
        closed_at=_iso(row["closed_at"]),
        created_at=_iso(row["created_at"]),
        updated_at=_iso(row["updated_at"]),
    )


class IncidentStore:
    """Persists incident records to the PostgreSQL incident_records table.

    Each row is one operator-facing incident: open / acknowledged / resolved.
    Used by the orchestrator /incidents API and by the retry-scheduler when a
    terminal failure needs to be surfaced. Mock-safe: it writes a row only —
    no external notifier is contacted from here.
    """

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.database_url, timeout=5)

    async def create_incident(
        self,
        *,
        severity: str,
        source: str,
        summary: str,
        task_id: str | None = None,
        workflow_id: str | None = None,
        details: dict[str, Any] | None = None,
        status: str = "open",
        normalized_severity: str | None = None,
        postmortem_required: bool = False,
    ) -> Incident:
        from .severity import normalize_severity_v2, postmortem_required as pm_required

        sev = normalize_severity(severity)
        norm_sev = normalized_severity or normalize_severity_v2(severity)
        pm_req = postmortem_required or pm_required(norm_sev)
        st = normalize_status(status)
        with start_span(
            "incident_store.create",
            **{
                "db.table": "incident_records",
                "task_id": task_id or "",
                "workflow_id": workflow_id or "",
                "incident.severity": sev,
                "incident.source": source,
            },
        ):
            conn = await self._connect()
            try:
                row = await conn.fetchrow(
                    "INSERT INTO incident_records "
                    "(task_id, workflow_id, severity, normalized_severity, status, "
                    " source, summary, details, postmortem_required) "
                    "VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9) "
                    f"RETURNING {_COLUMNS}",
                    task_id,
                    workflow_id,
                    sev,
                    norm_sev,
                    st,
                    source,
                    summary,
                    json.dumps(details or {}),
                    pm_req,
                )
            finally:
                await conn.close()
            return _row_to_incident(row)

    async def get_incident(self, incident_id: str) -> Incident | None:
        with start_span(
            "incident_store.get",
            **{"db.table": "incident_records", "incident.id": incident_id},
        ):
            conn = await self._connect()
            try:
                row = await conn.fetchrow(
                    f"SELECT {_COLUMNS} FROM incident_records WHERE id = $1::uuid",
                    incident_id,
                )
            except (asyncpg.PostgresError, ValueError):
                row = None
            finally:
                await conn.close()
            return _row_to_incident(row) if row else None

    async def list_incidents(
        self,
        *,
        status: str | None = None,
        severity: str | None = None,
        task_id: str | None = None,
        workflow_id: str | None = None,
        limit: int = 200,
    ) -> list[Incident]:
        with start_span(
            "incident_store.list",
            **{
                "db.table": "incident_records",
                "filter.status": status or "",
                "filter.severity": severity or "",
                "filter.task_id": task_id or "",
                "filter.workflow_id": workflow_id or "",
            },
        ):
            conn = await self._connect()
            try:
                rows = await conn.fetch(
                    f"SELECT {_COLUMNS} FROM incident_records "
                    "WHERE ($1::text IS NULL OR status = $1) "
                    "AND ($2::text IS NULL OR severity = $2) "
                    "AND ($3::text IS NULL OR task_id = $3) "
                    "AND ($4::text IS NULL OR workflow_id = $4) "
                    "ORDER BY created_at DESC LIMIT $5",
                    status,
                    severity,
                    task_id,
                    workflow_id,
                    limit,
                )
            finally:
                await conn.close()
            return [_row_to_incident(row) for row in rows]

    async def ack_incident(self, incident_id: str) -> Incident | None:
        return await self._transition(
            incident_id,
            "acknowledged",
            timestamp_column="acknowledged_at",
        )

    async def resolve_incident(self, incident_id: str) -> Incident | None:
        return await self._transition(
            incident_id,
            "resolved",
            timestamp_column="resolved_at",
        )

    async def close_incident(self, incident_id: str) -> Incident | None:
        return await self._transition(
            incident_id,
            "closed",
            timestamp_column="closed_at",
        )

    async def reopen_incident(self, incident_id: str) -> Incident | None:
        with start_span(
            "incident_store.reopen",
            **{"db.table": "incident_records", "incident.id": incident_id},
        ):
            conn = await self._connect()
            try:
                row = await conn.fetchrow(
                    "UPDATE incident_records "
                    "SET status = 'open', updated_at = now(), closed_at = NULL "
                    "WHERE id = $1::uuid "
                    f"RETURNING {_COLUMNS}",
                    incident_id,
                )
            except (asyncpg.PostgresError, ValueError):
                row = None
            finally:
                await conn.close()
            return _row_to_incident(row) if row else None

    async def _transition(
        self, incident_id: str, target_status: str, timestamp_column: str
    ) -> Incident | None:
        with start_span(
            "incident_store.transition",
            **{
                "db.table": "incident_records",
                "incident.id": incident_id,
                "incident.target_status": target_status,
            },
        ):
            conn = await self._connect()
            try:
                # Set the lifecycle timestamp only on first transition; the
                # COALESCE makes ack -> ack idempotent.
                row = await conn.fetchrow(
                    "UPDATE incident_records "
                    f"SET status = $2, {timestamp_column} = "
                    f"COALESCE({timestamp_column}, now()), updated_at = now() "
                    "WHERE id = $1::uuid "
                    f"RETURNING {_COLUMNS}",
                    incident_id,
                    target_status,
                )
            except (asyncpg.PostgresError, ValueError):
                row = None
            finally:
                await conn.close()
            return _row_to_incident(row) if row else None
