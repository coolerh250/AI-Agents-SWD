"""asyncpg-backed AuditStore for audit_logs.

Stage 19 introduces a single write path into ``audit_logs`` — the audit-worker
consumes ``stream.audit`` and uses this store to persist normalized events.
The existing schema is preserved (the audit-service POST handler continues to
use the same table), so this store is additive.

Dedup:
    ``source_message_id`` (the Redis ``XADD`` id) is recorded under
    ``artifact_refs.source_message_id`` and tracked in a runtime cache to
    short-circuit the natural at-least-once delivery of a consumer group.
    The cache is bounded — a steady stream of new ids will evict older ones.
    No new database column is required.

    NOTE: the runtime cache lives in each worker process. If the audit-worker
    restarts before its in-memory cache is drained, two consecutive XREADGROUPs
    of the same un-acked message would each pass the cache check and we'd
    insert twice. The worker mitigates this by ACK-ing immediately after a
    successful INSERT (Stage 19 ACK strategy); the residual exposure is a
    crash *between* INSERT and XACK, which is unlikely and harmless beyond
    creating one duplicate row.
"""

from __future__ import annotations

import json
import os
from collections import OrderedDict
from typing import Any

import asyncpg

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"
_RETURNING = "id, task_id, agent, decision_type, summary, result, artifact_refs, created_at"
DEDUP_CACHE_SIZE = 4096


def _row_to_audit(row: asyncpg.Record) -> dict[str, Any]:
    refs = row["artifact_refs"]
    if isinstance(refs, str):
        try:
            refs = json.loads(refs)
        except (TypeError, ValueError):
            refs = {}
    return {
        "audit_id": str(row["id"]),
        "task_id": row["task_id"],
        "agent": row["agent"],
        "decision_type": row["decision_type"],
        "summary": row["summary"],
        "result": row["result"],
        "artifact_refs": refs,
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


class AuditStore:
    """asyncpg-backed reader+writer for the ``audit_logs`` table.

    Mock-safe: this only writes audit bookkeeping. It never touches deployment
    records, never runs production actions, and never reads secrets.
    """

    def __init__(
        self,
        dsn: str | None = None,
        *,
        dedup_cache_size: int = DEDUP_CACHE_SIZE,
    ) -> None:
        self.dsn = dsn or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
        self._dedup_cache: OrderedDict[str, None] = OrderedDict()
        self._dedup_cache_size = max(1, dedup_cache_size)

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.dsn, timeout=5)

    def _seen(self, source_message_id: str) -> bool:
        return bool(source_message_id) and source_message_id in self._dedup_cache

    def _remember(self, source_message_id: str) -> None:
        if not source_message_id:
            return
        self._dedup_cache[source_message_id] = None
        if len(self._dedup_cache) > self._dedup_cache_size:
            self._dedup_cache.popitem(last=False)

    async def write_audit_log(self, event: dict[str, Any]) -> dict[str, Any] | None:
        """Insert one normalized audit event into ``audit_logs``.

        Returns the persisted row dict, or ``None`` when the row was skipped
        because its ``source_message_id`` was already recently written.
        """
        artifact_refs = event.get("artifact_refs") or {}
        source_id = str(artifact_refs.get("source_message_id") or "")
        if self._seen(source_id):
            return None
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO audit_logs "
                "(task_id, agent, decision_type, summary, result, artifact_refs) "
                "VALUES ($1, $2, $3, $4, $5, $6::jsonb) "
                f"RETURNING {_RETURNING}",
                event.get("task_id"),
                event.get("agent"),
                event.get("decision_type"),
                event.get("summary"),
                event.get("result"),
                json.dumps(artifact_refs),
            )
        finally:
            await conn.close()
        self._remember(source_id)
        return _row_to_audit(row)

    async def get_audit_logs(self, task_id: str) -> list[dict[str, Any]]:
        """Return every audit_logs row for a given task_id."""
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                f"SELECT {_RETURNING} FROM audit_logs WHERE task_id = $1 ORDER BY created_at",
                task_id,
            )
        finally:
            await conn.close()
        return [_row_to_audit(row) for row in rows]

    async def list_audit_logs(
        self,
        *,
        decision_type: str | None = None,
        agent: str | None = None,
        task_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List audit_logs rows by any combination of filters (newest first)."""
        clauses: list[str] = []
        params: list[Any] = []
        if decision_type:
            params.append(decision_type)
            clauses.append(f"decision_type = ${len(params)}")
        if agent:
            params.append(agent)
            clauses.append(f"agent = ${len(params)}")
        if task_id:
            params.append(task_id)
            clauses.append(f"task_id = ${len(params)}")
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(max(1, min(int(limit or 100), 500)))
        sql = (
            f"SELECT {_RETURNING} FROM audit_logs "
            f"{where} ORDER BY created_at DESC LIMIT ${len(params)}"
        )
        conn = await self._connect()
        try:
            rows = await conn.fetch(sql, *params)
        finally:
            await conn.close()
        return [_row_to_audit(row) for row in rows]
