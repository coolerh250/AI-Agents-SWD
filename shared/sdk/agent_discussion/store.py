"""Stage 46 -- asyncpg store for agent discussion tables."""

from __future__ import annotations

import json
import os
from typing import Any

import asyncpg

from shared.sdk.agent_discussion.models import (
    DiscussionArtifact,
    DiscussionContribution,
    DiscussionParticipant,
    DiscussionSession,
)
from shared.sdk.observability.tracing import start_span

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"


def _iso(v: Any) -> str | None:
    return v.isoformat() if v is not None else None


def _dec(v: Any, fallback: Any) -> Any:
    if v is None:
        return fallback
    if isinstance(v, str):
        try:
            return json.loads(v)
        except (ValueError, TypeError):
            return fallback
    return v


class AgentDiscussionStore:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.database_url, timeout=5)

    async def create_discussion_session(self, session: DiscussionSession) -> str:
        with start_span(
            "agent_discussion.create_session", **{"db.table": "agent_discussion_sessions"}
        ):
            conn = await self._connect()
            try:
                row = await conn.fetchrow(
                    "INSERT INTO agent_discussion_sessions "
                    "(project_id, work_item_id, source_task_id, session_type, status, "
                    " review_mode, planning_only, created_by_agent, metadata) "
                    "VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7, $8, $9::jsonb) "
                    "RETURNING id",
                    session.project_id,
                    session.work_item_id,
                    session.source_task_id,
                    session.session_type,
                    session.status,
                    session.review_mode,
                    session.planning_only,
                    session.created_by_agent,
                    json.dumps(session.metadata or {}),
                )
            finally:
                await conn.close()
            return str(row["id"])

    async def add_participants(
        self, session_id: str, participants: list[DiscussionParticipant]
    ) -> int:
        if not participants:
            return 0
        conn = await self._connect()
        try:
            async with conn.transaction():
                for p in participants:
                    await conn.execute(
                        "INSERT INTO agent_discussion_participants "
                        "(session_id, agent_role, participation_type, status, metadata) "
                        "VALUES ($1::uuid, $2, $3, $4, $5::jsonb)",
                        session_id,
                        p.agent_role,
                        p.participation_type,
                        p.status,
                        json.dumps(p.metadata or {}),
                    )
        finally:
            await conn.close()
        return len(participants)

    async def add_contributions(
        self,
        session_id: str,
        contributions: list[DiscussionContribution],
        *,
        project_id: str | None = None,
    ) -> int:
        if not contributions:
            return 0
        conn = await self._connect()
        try:
            async with conn.transaction():
                for c in contributions:
                    await conn.execute(
                        "INSERT INTO agent_discussion_contributions "
                        "(session_id, project_id, agent_role, contribution_type, summary, "
                        " rationale_summary, confidence, severity, related_artifact_refs, "
                        " metadata) "
                        "VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8, $9::jsonb, $10::jsonb)",
                        session_id,
                        project_id,
                        c.agent_role,
                        c.contribution_type,
                        c.summary,
                        c.rationale_summary,
                        c.confidence,
                        c.severity,
                        json.dumps(c.related_artifact_refs or []),
                        json.dumps(c.metadata or {}),
                    )
        finally:
            await conn.close()
        return len(contributions)

    async def add_discussion_artifact(
        self, session_id: str, artifact: DiscussionArtifact, *, project_id: str | None = None
    ) -> str:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO agent_discussion_artifacts "
                "(session_id, project_id, artifact_type, title, content, uri, "
                " created_by_agent, metadata) "
                "VALUES ($1::uuid, $2::uuid, $3, $4, $5::jsonb, $6, $7, $8::jsonb) RETURNING id",
                session_id,
                project_id,
                artifact.artifact_type,
                artifact.title,
                json.dumps(artifact.content) if artifact.content is not None else None,
                artifact.uri,
                artifact.created_by_agent,
                json.dumps(artifact.metadata or {}),
            )
        finally:
            await conn.close()
        return str(row["id"])

    async def complete_session(self, session_id: str, status: str = "completed") -> None:
        conn = await self._connect()
        try:
            await conn.execute(
                "UPDATE agent_discussion_sessions SET status = $2, updated_at = now(), "
                " completed_at = now() WHERE id = $1::uuid",
                session_id,
                status,
            )
        finally:
            await conn.close()

    # ---- reads ----
    async def get_session(self, session_id: str) -> dict | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT id, project_id, work_item_id, source_task_id, session_type, status, "
                " review_mode, planning_only, created_by_agent, created_at, completed_at, metadata "
                "FROM agent_discussion_sessions WHERE id = $1::uuid",
                session_id,
            )
        except (asyncpg.PostgresError, ValueError):
            row = None
        finally:
            await conn.close()
        if not row:
            return None
        return {
            "id": str(row["id"]),
            "project_id": str(row["project_id"]) if row["project_id"] else None,
            "work_item_id": str(row["work_item_id"]) if row["work_item_id"] else None,
            "session_type": row["session_type"],
            "status": row["status"],
            "review_mode": row["review_mode"],
            "planning_only": row["planning_only"],
            "created_by_agent": row["created_by_agent"],
            "created_at": _iso(row["created_at"]),
            "completed_at": _iso(row["completed_at"]),
            "metadata": _dec(row["metadata"], {}),
        }

    async def list_project_discussions(self, project_id: str) -> list[dict]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT id, session_type, status, review_mode, planning_only, created_at "
                "FROM agent_discussion_sessions WHERE project_id = $1::uuid "
                "ORDER BY created_at DESC",
                project_id,
            )
        finally:
            await conn.close()
        return [
            {
                "id": str(r["id"]),
                "session_type": r["session_type"],
                "status": r["status"],
                "review_mode": r["review_mode"],
                "planning_only": r["planning_only"],
                "created_at": _iso(r["created_at"]),
            }
            for r in rows
        ]

    async def list_participants(self, session_id: str) -> list[dict]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT agent_role, participation_type, status FROM agent_discussion_participants "
                "WHERE session_id = $1::uuid ORDER BY created_at",
                session_id,
            )
        finally:
            await conn.close()
        return [
            {
                "agent_role": r["agent_role"],
                "participation_type": r["participation_type"],
                "status": r["status"],
            }
            for r in rows
        ]

    async def list_contributions(self, session_id: str) -> list[dict]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT agent_role, contribution_type, summary, rationale_summary, confidence, "
                " severity, related_artifact_refs FROM agent_discussion_contributions "
                "WHERE session_id = $1::uuid ORDER BY created_at",
                session_id,
            )
        finally:
            await conn.close()
        return [
            {
                "agent_role": r["agent_role"],
                "contribution_type": r["contribution_type"],
                "summary": r["summary"],
                "rationale_summary": r["rationale_summary"],
                "confidence": r["confidence"],
                "severity": r["severity"],
                "related_artifact_refs": _dec(r["related_artifact_refs"], []),
            }
            for r in rows
        ]

    async def list_artifacts(self, session_id: str) -> list[dict]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT artifact_type, title, uri, created_by_agent FROM agent_discussion_artifacts "
                "WHERE session_id = $1::uuid ORDER BY created_at",
                session_id,
            )
        finally:
            await conn.close()
        return [
            {
                "artifact_type": r["artifact_type"],
                "title": r["title"],
                "uri": r["uri"],
                "created_by_agent": r["created_by_agent"],
            }
            for r in rows
        ]


__all__ = ["AgentDiscussionStore", "DEFAULT_DATABASE_URL"]
