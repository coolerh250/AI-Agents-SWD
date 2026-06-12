"""Stage 40 -- persistence layer for incident_alerts."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

import asyncpg

from .dedupe import compute_dedupe_key
from .normalizer import NormalizedAlert
from .redaction import payload_hash, redact_payload

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _parse_jsonb(value: Any) -> dict[str, Any]:
    """Safely decode a JSONB column — asyncpg may return str or dict."""
    if value is None:
        return {}
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
            return decoded if isinstance(decoded, dict) else {}
        except (ValueError, TypeError):
            return {}
    if isinstance(value, dict):
        return dict(value)
    return {}


def _row_to_dict(row: asyncpg.Record) -> dict[str, Any]:
    return {
        "alert_id": str(row["alert_id"]),
        "external_alert_id": row["external_alert_id"],
        "source": row["source"],
        "source_type": row["source_type"],
        "alert_name": row["alert_name"],
        "severity": row["severity"],
        "normalized_severity": row["normalized_severity"],
        "status": row["status"],
        "labels": _parse_jsonb(row["labels"]),
        "annotations": _parse_jsonb(row["annotations"]),
        "raw_payload_hash": row["raw_payload_hash"],
        "raw_payload_redacted": _parse_jsonb(row["raw_payload_redacted"]),
        "received_at": _iso(row["received_at"]),
        "starts_at": _iso(row["starts_at"]),
        "ends_at": _iso(row["ends_at"]),
        "fingerprint": row["fingerprint"],
        "dedupe_key": row["dedupe_key"],
        "incident_id": str(row["incident_id"]) if row["incident_id"] else None,
        "created_at": _iso(row["created_at"]),
        "updated_at": _iso(row["updated_at"]),
        "metadata": _parse_jsonb(row["metadata"]),
    }


class AlertStore:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.database_url, timeout=5)

    async def create_alert(
        self,
        alert: NormalizedAlert,
        *,
        raw_payload: Any = None,
        status: str = "received",
        incident_id: str | None = None,
    ) -> dict[str, Any]:
        dedupe_key = compute_dedupe_key(
            source=alert.source,
            alert_name=alert.alert_name,
            fingerprint=alert.fingerprint,
            labels=alert.labels,
        )
        raw_hash = payload_hash(raw_payload) if raw_payload is not None else None
        redacted = redact_payload(raw_payload) if raw_payload is not None else {}
        safe_labels = redact_payload(dict(alert.labels))
        safe_annotations = redact_payload(dict(alert.annotations))
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO incident_alerts
                  (external_alert_id, source, source_type, alert_name,
                   severity, normalized_severity, status,
                   labels, annotations, raw_payload_hash, raw_payload_redacted,
                   starts_at, ends_at, fingerprint, dedupe_key, incident_id)
                VALUES ($1,$2,$3,$4,$5,$6,$7,
                        $8::jsonb,$9::jsonb,$10,$11::jsonb,
                        $12,$13,$14,$15,$16::uuid)
                RETURNING *
                """,
                alert.external_alert_id,
                alert.source,
                alert.source_type,
                alert.alert_name,
                alert.severity,
                alert.normalized_severity,
                status,
                json.dumps(safe_labels),
                json.dumps(safe_annotations),
                raw_hash,
                json.dumps(redacted),
                alert.starts_at,
                alert.ends_at,
                alert.fingerprint,
                dedupe_key,
                incident_id,
            )
        finally:
            await conn.close()
        return _row_to_dict(row)

    async def link_alert_to_incident(
        self, alert_id: str, incident_id: str
    ) -> dict[str, Any] | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                """
                UPDATE incident_alerts
                SET    incident_id = $2::uuid,
                       status = 'linked_to_incident',
                       updated_at = now()
                WHERE  alert_id = $1::uuid
                RETURNING *
                """,
                alert_id,
                incident_id,
            )
        finally:
            await conn.close()
        return _row_to_dict(row) if row else None

    async def find_open_incident_by_dedupe(self, dedupe_key: str) -> str | None:
        """Return the incident_id for an open incident that matches dedupe_key."""
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                """
                SELECT ia.incident_id
                FROM   incident_alerts ia
                JOIN   incident_records ir ON ir.id = ia.incident_id
                WHERE  ia.dedupe_key = $1
                  AND  ir.status NOT IN ('resolved','closed')
                LIMIT  1
                """,
                dedupe_key,
            )
        finally:
            await conn.close()
        return str(row["incident_id"]) if row else None

    async def list_alerts_for_incident(self, incident_id: str) -> list[dict[str, Any]]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT * FROM incident_alerts WHERE incident_id = $1::uuid ORDER BY received_at",
                incident_id,
            )
        except (asyncpg.PostgresError, ValueError):
            rows = []
        finally:
            await conn.close()
        return [_row_to_dict(r) for r in rows]

    async def get_alert(self, alert_id: str) -> dict[str, Any] | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT * FROM incident_alerts WHERE alert_id = $1::uuid",
                alert_id,
            )
        except (asyncpg.PostgresError, ValueError):
            row = None
        finally:
            await conn.close()
        return _row_to_dict(row) if row else None

    async def count_rejected(self) -> int:
        conn = await self._connect()
        try:
            val = await conn.fetchval(
                "SELECT count(*) FROM incident_alerts WHERE status = 'rejected'"
            )
        finally:
            await conn.close()
        return int(val or 0)

    async def last_received_at(self) -> str | None:
        conn = await self._connect()
        try:
            val = await conn.fetchval("SELECT max(received_at) FROM incident_alerts")
        finally:
            await conn.close()
        return _iso(val)


__all__ = ["AlertStore"]
