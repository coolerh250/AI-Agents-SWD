"""Step 60 -- asyncpg store for release governance models.

Persists release candidates, deployment intents, evidence packages, readiness decisions,
and audit events with project / work-item / delivery-package linkage. target_environment
can never be production; production_ready / production_executed default false.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

import asyncpg

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"


class ReleaseGovernanceStore:
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

    async def create_candidate(
        self,
        *,
        candidate_id: str,
        project_id: str | None,
        version_label: str,
        target_environment: str,
        work_item_ids: list[str],
        delivery_package_ids: list[str],
        sandbox_draft_pr_ids: list[str],
        status: str,
        readiness_status: str,
    ) -> dict[str, Any]:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO release_candidates
                  (id, project_id, version_label, target_environment, work_item_ids,
                   delivery_package_ids, sandbox_draft_pr_ids, status, readiness_status)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                RETURNING id, project_id, version_label, target_environment, work_item_ids,
                          delivery_package_ids, sandbox_draft_pr_ids, status, readiness_status,
                          production_ready, created_at
                """,
                uuid.UUID(candidate_id),
                uuid.UUID(project_id) if project_id else None,
                version_label,
                target_environment,
                json.dumps(work_item_ids),
                json.dumps(delivery_package_ids),
                json.dumps(sandbox_draft_pr_ids),
                status,
                readiness_status,
            )
            return self._row(row)  # type: ignore[return-value]
        finally:
            await conn.close()

    async def get_candidate(self, candidate_id: str) -> dict[str, Any] | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT * FROM release_candidates WHERE id=$1", uuid.UUID(candidate_id)
            )
            return self._row(row)
        finally:
            await conn.close()

    async def list_candidates(self, limit: int = 100) -> list[dict[str, Any]]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT * FROM release_candidates ORDER BY created_at DESC LIMIT $1", int(limit)
            )
            return [self._row(r) for r in rows]  # type: ignore[misc]
        finally:
            await conn.close()

    async def create_intent(
        self,
        *,
        intent_id: str,
        candidate_id: str,
        target_environment: str,
        requested_action: str,
        status: str,
        policy_decision: str,
        requires_human_approval: bool,
        blocked_reason: str | None,
    ) -> dict[str, Any]:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO deployment_intents
                  (id, release_candidate_id, target_environment, requested_action, status,
                   policy_decision, requires_human_approval, blocked_reason)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                RETURNING id, release_candidate_id, target_environment, requested_action, status,
                          policy_decision, requires_human_approval, blocked_reason,
                          production_executed, created_at
                """,
                uuid.UUID(intent_id),
                uuid.UUID(candidate_id),
                target_environment,
                requested_action,
                status,
                policy_decision,
                requires_human_approval,
                blocked_reason,
            )
            return self._row(row)  # type: ignore[return-value]
        finally:
            await conn.close()

    async def get_intent(self, intent_id: str) -> dict[str, Any] | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT * FROM deployment_intents WHERE id=$1", uuid.UUID(intent_id)
            )
            return self._row(row)
        finally:
            await conn.close()

    async def list_intents(self, limit: int = 100) -> list[dict[str, Any]]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT * FROM deployment_intents ORDER BY created_at DESC LIMIT $1", int(limit)
            )
            return [self._row(r) for r in rows]  # type: ignore[misc]
        finally:
            await conn.close()

    async def counts(self) -> dict[str, int]:
        """Production-target / production-ready counts (expected 0)."""
        conn = await self._connect()
        try:
            rc_prod_ready = await conn.fetchval(
                "SELECT count(*) FROM release_candidates WHERE production_ready=true"
            )
            di_prod_target = await conn.fetchval(
                "SELECT count(*) FROM deployment_intents "
                "WHERE target_environment IN ('production','prod')"
            )
            di_prod_exec = await conn.fetchval(
                "SELECT count(*) FROM deployment_intents WHERE production_executed=true"
            )
            return {
                "release_candidate_production_ready_count": int(rc_prod_ready or 0),
                "deployment_intent_production_target_count": int(di_prod_target or 0),
                "deployment_intent_production_executed_count": int(di_prod_exec or 0),
            }
        finally:
            await conn.close()


__all__ = ["ReleaseGovernanceStore"]
