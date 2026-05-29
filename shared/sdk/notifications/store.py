"""asyncpg-backed NotificationDeliveryStore for ``notification_deliveries``.

Stage 22 introduces a per-notification delivery record so the operations
view can answer "did the platform notify the operator and how?" without
guessing. The store is intentionally small — every method is a single
SQL statement; the dedup contract is owned by the
``uq_notification_deliveries_source_message_id`` partial unique index
the migration adds.

The same row layout is used by:

* sandbox deliveries (``status='simulated', sandbox=True, external_sent=False``)
* real Discord deliveries (``status='delivered', sandbox=False,
  external_sent=True, message_id=<discord-id>``)
* failed deliveries (``status='failed', error=<reason>``)
* explicit skips (``status='skipped'``).
"""

from __future__ import annotations

import json
import os
from typing import Any

import asyncpg

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"
_RETURNING = (
    "id, task_id, event_type, channel, target, status, sandbox, external_sent, "
    "message_id, error, source_message_id, metadata, created_at, delivered_at"
)


def _decode_json(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return value
    return value


def _row_to_delivery(row: asyncpg.Record) -> dict[str, Any]:
    return {
        "delivery_id": str(row["id"]),
        "task_id": row["task_id"],
        "event_type": row["event_type"],
        "channel": row["channel"],
        "target": row["target"],
        "status": row["status"],
        "sandbox": bool(row["sandbox"]),
        "external_sent": bool(row["external_sent"]),
        "message_id": row["message_id"],
        "error": row["error"],
        "source_message_id": row["source_message_id"],
        "metadata": _decode_json(row["metadata"]) if row["metadata"] is not None else {},
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "delivered_at": row["delivered_at"].isoformat() if row["delivered_at"] else None,
    }


class NotificationDeliveryStore:
    """Async reader+writer for the ``notification_deliveries`` table.

    Mock-safe — only writes notification bookkeeping. Never reads or
    writes a secret. Never deploys to production. Never contacts an
    external service from inside the store.
    """

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.database_url, timeout=5)

    async def create_delivery(
        self,
        *,
        task_id: str | None,
        event_type: str,
        channel: str,
        target: str | None,
        status: str,
        sandbox: bool,
        external_sent: bool,
        message_id: str | None = None,
        error: str | None = None,
        source_message_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Insert one delivery row. Returns ``None`` when the
        ``source_message_id`` is already recorded (dedup).
        """
        meta_json = json.dumps(metadata or {})
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO notification_deliveries "
                "(task_id, event_type, channel, target, status, sandbox, "
                "external_sent, message_id, error, source_message_id, metadata) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb) "
                "ON CONFLICT (source_message_id) DO NOTHING "
                f"RETURNING {_RETURNING}",
                task_id,
                event_type,
                channel,
                target,
                status,
                sandbox,
                external_sent,
                message_id,
                error,
                source_message_id,
                meta_json,
            )
        finally:
            await conn.close()
        if row is None:
            return None
        return _row_to_delivery(row)

    async def get_delivery(self, delivery_id: str) -> dict[str, Any] | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                f"SELECT {_RETURNING} FROM notification_deliveries WHERE id = $1",
                delivery_id,
            )
        finally:
            await conn.close()
        return _row_to_delivery(row) if row else None

    async def list_deliveries(
        self,
        *,
        task_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if task_id:
            params.append(task_id)
            clauses.append(f"task_id = ${len(params)}")
        if status:
            params.append(status)
            clauses.append(f"status = ${len(params)}")
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(max(1, min(int(limit or 100), 500)))
        sql = (
            f"SELECT {_RETURNING} FROM notification_deliveries "
            f"{where} ORDER BY created_at DESC LIMIT ${len(params)}"
        )
        conn = await self._connect()
        try:
            rows = await conn.fetch(sql, *params)
        finally:
            await conn.close()
        return [_row_to_delivery(row) for row in rows]

    async def mark_delivered(
        self,
        delivery_id: str,
        *,
        message_id: str | None = None,
        external_sent: bool = True,
    ) -> dict[str, Any] | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "UPDATE notification_deliveries "
                "SET status = 'delivered', delivered_at = now(), "
                "message_id = COALESCE($2, message_id), "
                "external_sent = $3 "
                f"WHERE id = $1 RETURNING {_RETURNING}",
                delivery_id,
                message_id,
                external_sent,
            )
        finally:
            await conn.close()
        return _row_to_delivery(row) if row else None

    async def mark_failed(
        self,
        delivery_id: str,
        *,
        error: str,
    ) -> dict[str, Any] | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "UPDATE notification_deliveries "
                "SET status = 'failed', error = $2, delivered_at = now() "
                f"WHERE id = $1 RETURNING {_RETURNING}",
                delivery_id,
                error,
            )
        finally:
            await conn.close()
        return _row_to_delivery(row) if row else None

    async def counts(self, *, task_id: str | None = None) -> dict[str, int]:
        """Return aggregated counters for the operations summary."""
        clauses: list[str] = []
        params: list[Any] = []
        if task_id:
            params.append(task_id)
            clauses.append(f"task_id = ${len(params)}")
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = (
            "SELECT "
            "  COUNT(*) AS total, "
            "  COUNT(*) FILTER (WHERE status='simulated') AS simulated, "
            "  COUNT(*) FILTER (WHERE status='delivered') AS delivered, "
            "  COUNT(*) FILTER (WHERE status='failed') AS failed, "
            "  COUNT(*) FILTER (WHERE status='skipped') AS skipped, "
            "  COUNT(*) FILTER (WHERE external_sent=true) AS external_sent "
            f"FROM notification_deliveries {where}"
        )
        conn = await self._connect()
        try:
            row = await conn.fetchrow(sql, *params)
        finally:
            await conn.close()
        if row is None:
            return {
                "total": 0,
                "simulated": 0,
                "delivered": 0,
                "failed": 0,
                "skipped": 0,
                "external_sent": 0,
            }
        return {
            "total": int(row["total"] or 0),
            "simulated": int(row["simulated"] or 0),
            "delivered": int(row["delivered"] or 0),
            "failed": int(row["failed"] or 0),
            "skipped": int(row["skipped"] or 0),
            "external_sent": int(row["external_sent"] or 0),
        }
