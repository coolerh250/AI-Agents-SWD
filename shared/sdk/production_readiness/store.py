"""Step 62 -- asyncpg store for production readiness gate models.

Persists readiness decisions and operator review packages. production_ready /
production_approved / production_action_allowed / production_executed default false; a row
is a governance artifact only: NOT a deploy, NOT an approval, NOT a production action.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

import asyncpg

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"


class ProductionReadinessStore:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.database_url, timeout=5)

    @staticmethod
    def _row(row: asyncpg.Record | None) -> dict[str, Any] | None:
        if row is None:
            return None
        d = dict(row)
        for k, v in list(d.items()):
            if isinstance(v, uuid.UUID):
                d[k] = str(v)
            elif hasattr(v, "isoformat"):
                d[k] = v.isoformat()
        return d

    async def create_decision(
        self, *, decision_id: str, decision: str, blockers: list[str], missing_evidence: list[str]
    ) -> dict[str, Any]:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO production_readiness_decisions
                  (id, decision, blockers, missing_evidence)
                VALUES ($1,$2,$3,$4)
                RETURNING id, decision, blockers, missing_evidence, production_ready,
                          production_approved, production_action_allowed, created_at
                """,
                uuid.UUID(decision_id),
                decision,
                json.dumps(blockers),
                json.dumps(missing_evidence),
            )
            return self._row(row)  # type: ignore[return-value]
        finally:
            await conn.close()

    async def create_operator_review_request(
        self, *, request_id: str, decision_status: str, summary: dict[str, Any]
    ) -> dict[str, Any]:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO operator_review_packages (id, decision_status, summary)
                VALUES ($1,$2,$3)
                RETURNING id, decision_status, summary, production_ready, production_approved,
                          production_action_allowed, created_at
                """,
                uuid.UUID(request_id),
                decision_status,
                json.dumps(summary),
            )
            return self._row(row)  # type: ignore[return-value]
        finally:
            await conn.close()

    async def list_operator_review_requests(self, limit: int = 100) -> list[dict[str, Any]]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT * FROM operator_review_packages ORDER BY created_at DESC LIMIT $1",
                int(limit),
            )
            return [self._row(r) for r in rows]  # type: ignore[misc]
        finally:
            await conn.close()

    async def counts(self) -> dict[str, int]:
        """Production-action executed counts (expected 0)."""
        conn = await self._connect()
        try:
            executed = await conn.fetchval(
                "SELECT count(*) FROM production_readiness_decisions WHERE production_executed=true"
            )
            n = int(executed or 0)
            return {
                "production_deployment_executed_count": n,
                "production_sync_executed_count": n,
                "production_restore_executed_count": n,
                "production_failover_executed_count": n,
            }
        finally:
            await conn.close()


__all__ = ["ProductionReadinessStore"]
