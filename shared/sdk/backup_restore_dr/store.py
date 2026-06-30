"""Step 61 -- asyncpg store for backup / restore / DR governance models.

Persists cleanup reviews, restore plans, restore validations, DR operations, and recovery
evidence packages. target_environment can never be production (CHECK); production_restore /
production_failover / production_executed default false. A row is a governance artifact
only: NOT a restore, NOT a failover, NOT a cleanup execution.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

import asyncpg

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"


class BackupRestoreDrStore:
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

    async def create_cleanup_review(
        self,
        *,
        review_id: str,
        scope: str,
        candidates: list[dict[str, Any]],
        allowed_count: int,
        blocked_count: int,
        requires_approval_count: int,
        risk_level: str,
    ) -> dict[str, Any]:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO cleanup_reviews
                  (id, scope, candidates, allowed_count, blocked_count,
                   requires_approval_count, risk_level)
                VALUES ($1,$2,$3,$4,$5,$6,$7)
                RETURNING id, scope, candidates, allowed_count, blocked_count,
                          requires_approval_count, risk_level, cleanup_executed, created_at
                """,
                uuid.UUID(review_id),
                scope,
                json.dumps(candidates),
                int(allowed_count),
                int(blocked_count),
                int(requires_approval_count),
                risk_level,
            )
            return self._row(row)  # type: ignore[return-value]
        finally:
            await conn.close()

    async def list_cleanup_reviews(self, limit: int = 100) -> list[dict[str, Any]]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT * FROM cleanup_reviews ORDER BY created_at DESC LIMIT $1", int(limit)
            )
            return [self._row(r) for r in rows]  # type: ignore[misc]
        finally:
            await conn.close()

    async def create_restore_plan(
        self,
        *,
        plan_id: str,
        target: str,
        source_artifact: str | None,
        target_environment: str,
        restore_type: str,
        status: str,
        policy_decision: str,
        requires_human_approval: bool,
        blocked_reason: str | None,
    ) -> dict[str, Any]:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO restore_plans
                  (id, target, source_artifact, target_environment, restore_type, status,
                   policy_decision, requires_human_approval, blocked_reason)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                RETURNING id, target, source_artifact, target_environment, restore_type,
                          status, policy_decision, requires_human_approval, blocked_reason,
                          production_restore, created_at
                """,
                uuid.UUID(plan_id),
                target,
                source_artifact,
                target_environment,
                restore_type,
                status,
                policy_decision,
                requires_human_approval,
                blocked_reason,
            )
            return self._row(row)  # type: ignore[return-value]
        finally:
            await conn.close()

    async def list_restore_plans(self, limit: int = 100) -> list[dict[str, Any]]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT * FROM restore_plans ORDER BY created_at DESC LIMIT $1", int(limit)
            )
            return [self._row(r) for r in rows]  # type: ignore[misc]
        finally:
            await conn.close()

    async def list_restore_validations(self, limit: int = 100) -> list[dict[str, Any]]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT * FROM restore_validations ORDER BY created_at DESC LIMIT $1", int(limit)
            )
            return [self._row(r) for r in rows]  # type: ignore[misc]
        finally:
            await conn.close()

    async def list_dr_operations(self, limit: int = 100) -> list[dict[str, Any]]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT * FROM dr_operations ORDER BY created_at DESC LIMIT $1", int(limit)
            )
            return [self._row(r) for r in rows]  # type: ignore[misc]
        finally:
            await conn.close()

    async def counts(self) -> dict[str, int]:
        """Production restore / failover plan + executed counts (expected 0)."""
        conn = await self._connect()
        try:
            prod_restore_plans = await conn.fetchval(
                "SELECT count(*) FROM restore_plans "
                "WHERE target_environment IN ('production','prod') OR production_restore=true"
            )
            prod_failover_plans = await conn.fetchval(
                "SELECT count(*) FROM dr_operations "
                "WHERE operation_type IN ('production_failover','cross_region_failover')"
            )
            prod_restore_exec = await conn.fetchval(
                "SELECT count(*) FROM restore_validations WHERE production_executed=true"
            )
            prod_failover_exec = await conn.fetchval(
                "SELECT count(*) FROM dr_operations WHERE production_executed=true"
            )
            return {
                "production_restore_plan_count": int(prod_restore_plans or 0),
                "production_failover_plan_count": int(prod_failover_plans or 0),
                "production_restore_executed_count": int(prod_restore_exec or 0),
                "production_failover_executed_count": int(prod_failover_exec or 0),
            }
        finally:
            await conn.close()


__all__ = ["BackupRestoreDrStore"]
