"""Stage 46 -- asyncpg store for design review tables."""

from __future__ import annotations

import json
import os
from typing import Any

import asyncpg

from shared.sdk.design_review.models import (
    DesignReviewDecision,
    DesignReviewFinding,
    DesignReviewSession,
    ProjectReviewGate,
)
from shared.sdk.observability.tracing import start_span

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"


def _iso(v: Any) -> str | None:
    return v.isoformat() if v is not None else None


class DesignReviewStore:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.database_url, timeout=5)

    async def create_design_review_session(self, session: DesignReviewSession) -> str:
        with start_span("design_review.create_session", **{"db.table": "design_review_sessions"}):
            conn = await self._connect()
            try:
                row = await conn.fetchrow(
                    "INSERT INTO design_review_sessions "
                    "(discussion_session_id, project_id, graph_snapshot_id, review_type, "
                    " status, decision, metadata) "
                    "VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7::jsonb) RETURNING id",
                    session.discussion_session_id,
                    session.project_id,
                    session.graph_snapshot_id,
                    session.review_type,
                    session.status,
                    session.decision,
                    json.dumps(session.metadata or {}),
                )
            finally:
                await conn.close()
            return str(row["id"])

    async def finalize_review_session(
        self, review_session_id: str, *, status: str, decision: str
    ) -> None:
        conn = await self._connect()
        try:
            await conn.execute(
                "UPDATE design_review_sessions SET status = $2, decision = $3, "
                " completed_at = now() WHERE id = $1::uuid",
                review_session_id,
                status,
                decision,
            )
        finally:
            await conn.close()

    async def add_findings(
        self, review_session_id: str, project_id: str, findings: list[DesignReviewFinding]
    ) -> int:
        if not findings:
            return 0
        conn = await self._connect()
        try:
            async with conn.transaction():
                for f in findings:
                    await conn.execute(
                        "INSERT INTO design_review_findings "
                        "(review_session_id, project_id, finding_key, finding_type, severity, "
                        " title, description, recommendation, status, created_by_agent, metadata) "
                        "VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb)",
                        review_session_id,
                        project_id,
                        f.finding_key,
                        f.finding_type,
                        f.severity,
                        f.title,
                        f.description,
                        f.recommendation,
                        f.status,
                        f.created_by_agent,
                        json.dumps(f.metadata or {}),
                    )
        finally:
            await conn.close()
        return len(findings)

    async def add_decisions(
        self, review_session_id: str, project_id: str, decisions: list[DesignReviewDecision]
    ) -> int:
        if not decisions:
            return 0
        conn = await self._connect()
        try:
            async with conn.transaction():
                for d in decisions:
                    await conn.execute(
                        "INSERT INTO design_review_decisions "
                        "(review_session_id, project_id, decision_type, decision, "
                        " rationale_summary, decided_by, approval_required, approval_status, "
                        " metadata) "
                        "VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8, $9::jsonb)",
                        review_session_id,
                        project_id,
                        d.decision_type,
                        d.decision,
                        d.rationale_summary,
                        d.decided_by,
                        d.approval_required,
                        d.approval_status,
                        json.dumps(d.metadata or {}),
                    )
        finally:
            await conn.close()
        return len(decisions)

    async def upsert_review_gates(
        self, project_id: str, review_session_id: str, gates: list[ProjectReviewGate]
    ) -> int:
        if not gates:
            return 0
        conn = await self._connect()
        try:
            async with conn.transaction():
                for g in gates:
                    await conn.execute(
                        "INSERT INTO project_review_gates "
                        "(project_id, gate_type, status, required, blocking, "
                        " review_session_id, metadata) "
                        "VALUES ($1::uuid, $2, $3, $4, $5, $6::uuid, $7::jsonb) "
                        "ON CONFLICT (project_id, gate_type) DO UPDATE SET "
                        " status = EXCLUDED.status, required = EXCLUDED.required, "
                        " blocking = EXCLUDED.blocking, "
                        " review_session_id = EXCLUDED.review_session_id, "
                        " updated_at = now(), metadata = EXCLUDED.metadata",
                        project_id,
                        g.gate_type,
                        g.status,
                        g.required,
                        g.blocking,
                        review_session_id,
                        json.dumps(g.metadata or {}),
                    )
        finally:
            await conn.close()
        return len(gates)

    # ---- reads ----
    async def get_review(self, review_session_id: str) -> dict | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT id, project_id, discussion_session_id, graph_snapshot_id, review_type, "
                " status, decision, created_at, completed_at, metadata "
                "FROM design_review_sessions WHERE id = $1::uuid",
                review_session_id,
            )
        except (asyncpg.PostgresError, ValueError):
            row = None
        finally:
            await conn.close()
        if not row:
            return None
        return {
            "id": str(row["id"]),
            "project_id": str(row["project_id"]),
            "discussion_session_id": (
                str(row["discussion_session_id"]) if row["discussion_session_id"] else None
            ),
            "graph_snapshot_id": (
                str(row["graph_snapshot_id"]) if row["graph_snapshot_id"] else None
            ),
            "review_type": row["review_type"],
            "status": row["status"],
            "decision": row["decision"],
            "created_at": _iso(row["created_at"]),
            "completed_at": _iso(row["completed_at"]),
            "metadata": row["metadata"] if isinstance(row["metadata"], dict) else {},
        }

    async def list_project_reviews(self, project_id: str) -> list[dict]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT id, review_type, status, decision, created_at FROM design_review_sessions "
                "WHERE project_id = $1::uuid ORDER BY created_at DESC",
                project_id,
            )
        finally:
            await conn.close()
        return [
            {
                "id": str(r["id"]),
                "review_type": r["review_type"],
                "status": r["status"],
                "decision": r["decision"],
                "created_at": _iso(r["created_at"]),
            }
            for r in rows
        ]

    async def get_latest_review(self, project_id: str) -> dict | None:
        reviews = await self.list_project_reviews(project_id)
        if not reviews:
            return None
        return await self.get_review(reviews[0]["id"])

    async def list_findings(self, review_session_id: str) -> list[dict]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT finding_key, finding_type, severity, title, description, recommendation, "
                " status, created_by_agent FROM design_review_findings "
                "WHERE review_session_id = $1::uuid ORDER BY severity DESC, finding_key",
                review_session_id,
            )
        finally:
            await conn.close()
        return [dict(r) for r in rows]

    async def list_decisions(self, review_session_id: str) -> list[dict]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT decision_type, decision, rationale_summary, decided_by, "
                " approval_required, approval_status FROM design_review_decisions "
                "WHERE review_session_id = $1::uuid ORDER BY created_at",
                review_session_id,
            )
        finally:
            await conn.close()
        return [dict(r) for r in rows]

    async def list_gates(self, project_id: str) -> list[dict]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT gate_type, status, required, blocking FROM project_review_gates "
                "WHERE project_id = $1::uuid ORDER BY gate_type",
                project_id,
            )
        finally:
            await conn.close()
        return [dict(r) for r in rows]

    async def compute_review_summary(self, project_id: str) -> dict:
        review = await self.get_latest_review(project_id)
        gates = await self.list_gates(project_id)
        gates_passed = sum(1 for g in gates if g["status"] in ("passed", "passed_with_findings"))
        findings: list[dict] = []
        blocking = 0
        if review:
            findings = await self.list_findings(review["id"])
            blocking = len(
                [
                    f
                    for f in findings
                    if f["severity"] in ("high", "critical") and f["status"] == "open"
                ]
            )
        return {
            "project_id": project_id,
            "latest_review_status": review["status"] if review else None,
            "latest_review_decision": review["decision"] if review else None,
            "review_session_id": review["id"] if review else None,
            "findings_count": len(findings),
            "blocking_findings_count": blocking,
            "gates_total": len(gates),
            "gates_passed": gates_passed,
            "gates": gates,
            "planning_only": True,
            "production_executed": False,
        }


__all__ = ["DesignReviewStore", "DEFAULT_DATABASE_URL"]
