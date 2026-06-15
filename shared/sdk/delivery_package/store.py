"""Stage 49 -- asyncpg store for the delivery package / acceptance gate tables."""

from __future__ import annotations

import json
import os
from typing import Any

import asyncpg

from shared.sdk.delivery_package.models import (
    AcceptanceGateCheckResult,
    AcceptanceGateRun,
    DeliveryPackage,
    DeliveryPackageArtifact,
    DeliveryPackageSection,
    DeliveryReadinessSnapshot,
    HandoffSummary,
    OperatorAcceptanceReview,
)
from shared.sdk.observability.tracing import start_span

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"


def _iso(v: Any) -> str | None:
    return v.isoformat() if v is not None else None


def _dec(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return fallback
    return value


class DeliveryPackageStore:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.database_url, timeout=5)

    # ------------------------------------------------------------------ create
    async def create_delivery_package(self, package: DeliveryPackage) -> str:
        with start_span("delivery_package.create", **{"db.table": "delivery_packages"}):
            conn = await self._connect()
            try:
                row = await conn.fetchrow(
                    "INSERT INTO delivery_packages "
                    "(project_id, pilot_id, workspace_id, design_review_session_id, package_key, "
                    " package_type, status, controlled_only, human_acceptance_required, "
                    " human_acceptance_status, created_by_agent, metadata) "
                    "VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6, $7, $8, $9, $10, "
                    " $11, $12::jsonb) RETURNING id",
                    package.project_id,
                    package.pilot_id,
                    package.workspace_id,
                    package.design_review_session_id,
                    package.package_key,
                    package.package_type,
                    package.status,
                    package.controlled_only,
                    package.human_acceptance_required,
                    package.human_acceptance_status,
                    package.created_by_agent,
                    json.dumps(package.metadata or {}),
                )
            finally:
                await conn.close()
            return str(row["id"])

    async def update_package_status(
        self, package_id: str, status: str, *, completed: bool = False
    ) -> None:
        conn = await self._connect()
        try:
            await conn.execute(
                "UPDATE delivery_packages SET status = $2, updated_at = now(), "
                " completed_at = CASE WHEN $3 THEN now() ELSE completed_at END "
                "WHERE id = $1::uuid",
                package_id,
                status,
                completed,
            )
        finally:
            await conn.close()

    async def create_sections(
        self, package_id: str, project_id: str | None, sections: list[DeliveryPackageSection]
    ) -> int:
        if not sections:
            return 0
        conn = await self._connect()
        try:
            async with conn.transaction():
                for s in sections:
                    await conn.execute(
                        "INSERT INTO delivery_package_sections "
                        "(package_id, project_id, section_key, title, content, content_summary, "
                        " order_index, status, metadata) "
                        "VALUES ($1::uuid, $2::uuid, $3, $4, $5::jsonb, $6, $7, $8, $9::jsonb) "
                        "ON CONFLICT (package_id, section_key) DO UPDATE SET "
                        " content = EXCLUDED.content, content_summary = EXCLUDED.content_summary, "
                        " status = EXCLUDED.status",
                        package_id,
                        project_id,
                        s.section_key,
                        s.title,
                        json.dumps(s.content or {}),
                        s.content_summary,
                        s.order_index,
                        s.status,
                        json.dumps(s.metadata or {}),
                    )
        finally:
            await conn.close()
        return len(sections)

    async def create_artifacts(
        self, package_id: str, project_id: str | None, artifacts: list[DeliveryPackageArtifact]
    ) -> int:
        if not artifacts:
            return 0
        conn = await self._connect()
        try:
            async with conn.transaction():
                for a in artifacts:
                    await conn.execute(
                        "INSERT INTO delivery_package_artifacts "
                        "(package_id, project_id, artifact_type, source_table, source_id, title, "
                        " uri, content, metadata) "
                        "VALUES ($1::uuid, $2::uuid, $3, $4, $5::uuid, $6, $7, $8::jsonb, "
                        " $9::jsonb)",
                        package_id,
                        project_id,
                        a.artifact_type,
                        a.source_table,
                        a.source_id,
                        a.title,
                        a.uri,
                        json.dumps(a.content) if a.content is not None else None,
                        json.dumps(a.metadata or {}),
                    )
        finally:
            await conn.close()
        return len(artifacts)

    async def create_acceptance_gate_run(
        self, package_id: str, project_id: str | None, pilot_id: str | None, gate: AcceptanceGateRun
    ) -> str:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO acceptance_gate_runs "
                "(package_id, project_id, pilot_id, gate_key, gate_type, status, decision, "
                " human_review_required, human_review_status, blocking_findings_count, "
                " total_checks, passed_checks, failed_checks, warning_checks, completed_at, "
                " metadata) "
                "VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7, $8, $9, $10, $11, $12, "
                " $13, $14, now(), $15::jsonb) RETURNING id",
                package_id,
                project_id,
                pilot_id,
                gate.gate_key,
                gate.gate_type,
                gate.status,
                gate.decision,
                gate.human_review_required,
                gate.human_review_status,
                gate.blocking_findings_count,
                gate.total_checks,
                gate.passed_checks,
                gate.failed_checks,
                gate.warning_checks,
                json.dumps(gate.metadata or {}),
            )
        finally:
            await conn.close()
        return str(row["id"])

    async def create_gate_check_results(
        self,
        gate_run_id: str,
        package_id: str | None,
        project_id: str | None,
        checks: list[AcceptanceGateCheckResult],
    ) -> int:
        if not checks:
            return 0
        conn = await self._connect()
        try:
            async with conn.transaction():
                for c in checks:
                    await conn.execute(
                        "INSERT INTO acceptance_gate_check_results "
                        "(gate_run_id, package_id, project_id, check_key, check_type, status, "
                        " severity, blocking, evidence_ref, summary, metadata) "
                        "VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7, $8, $9::jsonb, $10, "
                        " $11::jsonb) ON CONFLICT (gate_run_id, check_key) DO NOTHING",
                        gate_run_id,
                        package_id,
                        project_id,
                        c.check_key,
                        c.check_type,
                        c.status,
                        c.severity,
                        c.blocking,
                        json.dumps(c.evidence_ref or {}),
                        c.summary,
                        json.dumps(c.metadata or {}),
                    )
        finally:
            await conn.close()
        return len(checks)

    async def create_operator_review_placeholder(
        self,
        package_id: str,
        project_id: str | None,
        gate_run_id: str | None,
        review: OperatorAcceptanceReview,
    ) -> str:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO operator_acceptance_reviews "
                "(package_id, project_id, gate_run_id, reviewer, review_status, review_summary, "
                " requested_changes, metadata) "
                "VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7::jsonb, $8::jsonb) "
                "RETURNING id",
                package_id,
                project_id,
                gate_run_id,
                review.reviewer,
                review.review_status,
                review.review_summary,
                json.dumps(review.requested_changes or []),
                json.dumps(review.metadata or {}),
            )
        finally:
            await conn.close()
        return str(row["id"])

    async def create_handoff_summaries(
        self, package_id: str, project_id: str | None, summaries: list[HandoffSummary]
    ) -> list[str]:
        if not summaries:
            return []
        ids: list[str] = []
        conn = await self._connect()
        try:
            async with conn.transaction():
                for h in summaries:
                    row = await conn.fetchrow(
                        "INSERT INTO handoff_summaries "
                        "(package_id, project_id, summary_type, title, summary, highlights, "
                        " limitations, next_steps, artifact_refs, created_by_agent, metadata) "
                        "VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6::jsonb, $7::jsonb, $8::jsonb, "
                        " $9::jsonb, $10, $11::jsonb) RETURNING id",
                        package_id,
                        project_id,
                        h.summary_type,
                        h.title,
                        h.summary,
                        json.dumps(h.highlights or []),
                        json.dumps(h.limitations or []),
                        json.dumps(h.next_steps or []),
                        json.dumps(h.artifact_refs or []),
                        h.created_by_agent,
                        json.dumps(h.metadata or {}),
                    )
                    ids.append(str(row["id"]))
        finally:
            await conn.close()
        return ids

    async def create_readiness_snapshot(
        self,
        package_id: str,
        project_id: str | None,
        pilot_id: str | None,
        snapshot: DeliveryReadinessSnapshot,
    ) -> str:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO delivery_readiness_snapshots "
                "(package_id, project_id, pilot_id, readiness_status, project_ready, design_ready, "
                " workspace_ready, qa_ready, acceptance_ready, safety_ready, docs_ready, "
                " human_acceptance_pending, blocking_reasons, warnings, metadata) "
                "VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7, $8, $9, $10, $11, $12, "
                " $13::jsonb, $14::jsonb, $15::jsonb) RETURNING id",
                package_id,
                project_id,
                pilot_id,
                snapshot.readiness_status,
                snapshot.project_ready,
                snapshot.design_ready,
                snapshot.workspace_ready,
                snapshot.qa_ready,
                snapshot.acceptance_ready,
                snapshot.safety_ready,
                snapshot.docs_ready,
                snapshot.human_acceptance_pending,
                json.dumps(snapshot.blocking_reasons or []),
                json.dumps(snapshot.warnings or []),
                json.dumps(snapshot.metadata or {}),
            )
        finally:
            await conn.close()
        return str(row["id"])

    async def set_package_report(self, package_id: str, report: dict) -> None:
        """Persist the delivery package report in delivery_packages.metadata."""
        conn = await self._connect()
        try:
            await conn.execute(
                "UPDATE delivery_packages SET metadata = "
                " jsonb_set(COALESCE(metadata, '{}'::jsonb), '{report}', $2::jsonb, true), "
                " updated_at = now() WHERE id = $1::uuid",
                package_id,
                json.dumps(report or {}),
            )
        finally:
            await conn.close()

    async def set_export_metadata(self, package_id: str, export_metadata: dict) -> None:
        conn = await self._connect()
        try:
            await conn.execute(
                "UPDATE delivery_packages SET metadata = "
                " jsonb_set(COALESCE(metadata, '{}'::jsonb), '{export_metadata}', $2::jsonb, true)"
                " , updated_at = now() WHERE id = $1::uuid",
                package_id,
                json.dumps(export_metadata or {}),
            )
        finally:
            await conn.close()

    # -------------------------------------------------------------------- reads
    _PKG_COLS = (
        "id, package_key, package_type, status, project_id, pilot_id, workspace_id, "
        "design_review_session_id, controlled_only, human_acceptance_required, "
        "human_acceptance_status, real_llm_enabled, github_write_enabled, pr_creation_enabled, "
        "deployment_enabled, external_delivery_enabled, production_executed, created_by_agent, "
        "created_at, completed_at, metadata"
    )

    @staticmethod
    def _pkg_row(r: asyncpg.Record) -> dict:
        return {
            "id": str(r["id"]),
            "package_key": r["package_key"],
            "package_type": r["package_type"],
            "status": r["status"],
            "project_id": str(r["project_id"]) if r["project_id"] else None,
            "pilot_id": str(r["pilot_id"]) if r["pilot_id"] else None,
            "workspace_id": str(r["workspace_id"]) if r["workspace_id"] else None,
            "design_review_session_id": (
                str(r["design_review_session_id"]) if r["design_review_session_id"] else None
            ),
            "controlled_only": r["controlled_only"],
            "human_acceptance_required": r["human_acceptance_required"],
            "human_acceptance_status": r["human_acceptance_status"],
            "real_llm_enabled": r["real_llm_enabled"],
            "github_write_enabled": r["github_write_enabled"],
            "pr_creation_enabled": r["pr_creation_enabled"],
            "deployment_enabled": r["deployment_enabled"],
            "external_delivery_enabled": r["external_delivery_enabled"],
            "production_executed": r["production_executed"],
            "created_by_agent": r["created_by_agent"],
            "created_at": _iso(r["created_at"]),
            "completed_at": _iso(r["completed_at"]),
            "metadata": _dec(r["metadata"], {}),
        }

    async def get_delivery_package(self, package_id: str) -> dict | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                f"SELECT {self._PKG_COLS} FROM delivery_packages WHERE id = $1::uuid",
                package_id,
            )
        except (asyncpg.PostgresError, ValueError):
            row = None
        finally:
            await conn.close()
        return self._pkg_row(row) if row else None

    async def list_delivery_packages(
        self, *, project_id: str | None = None, limit: int = 100
    ) -> list[dict]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                f"SELECT {self._PKG_COLS} FROM delivery_packages "
                "WHERE ($1::uuid IS NULL OR project_id = $1::uuid) "
                "ORDER BY created_at DESC LIMIT $2",
                project_id,
                max(1, min(int(limit), 500)),
            )
        finally:
            await conn.close()
        return [self._pkg_row(r) for r in rows]

    async def get_latest_package(self, project_id: str | None = None) -> dict | None:
        rows = await self.list_delivery_packages(project_id=project_id, limit=1)
        return rows[0] if rows else None

    async def get_package_sections(self, package_id: str) -> list[dict]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT section_key, title, content, content_summary, order_index, status "
                "FROM delivery_package_sections WHERE package_id = $1::uuid ORDER BY order_index",
                package_id,
            )
        finally:
            await conn.close()
        return [
            {
                "section_key": r["section_key"],
                "title": r["title"],
                "content": _dec(r["content"], {}),
                "content_summary": r["content_summary"],
                "order_index": r["order_index"],
                "status": r["status"],
            }
            for r in rows
        ]

    async def get_package_artifacts(self, package_id: str) -> list[dict]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT artifact_type, source_table, source_id, title, uri, content, created_at "
                "FROM delivery_package_artifacts WHERE package_id = $1::uuid ORDER BY created_at",
                package_id,
            )
        finally:
            await conn.close()
        return [
            {
                "artifact_type": r["artifact_type"],
                "source_table": r["source_table"],
                "source_id": str(r["source_id"]) if r["source_id"] else None,
                "title": r["title"],
                "uri": r["uri"],
                "content": _dec(r["content"], None),
                "created_at": _iso(r["created_at"]),
            }
            for r in rows
        ]

    async def get_acceptance_gate(self, package_id: str) -> dict | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT id, gate_key, gate_type, status, decision, human_review_required, "
                " human_review_status, blocking_findings_count, total_checks, passed_checks, "
                " failed_checks, warning_checks, created_at, completed_at "
                "FROM acceptance_gate_runs WHERE package_id = $1::uuid "
                "ORDER BY created_at DESC LIMIT 1",
                package_id,
            )
        finally:
            await conn.close()
        if not row:
            return None
        return {
            "id": str(row["id"]),
            "gate_key": row["gate_key"],
            "gate_type": row["gate_type"],
            "status": row["status"],
            "decision": row["decision"],
            "human_review_required": row["human_review_required"],
            "human_review_status": row["human_review_status"],
            "blocking_findings_count": row["blocking_findings_count"],
            "total_checks": row["total_checks"],
            "passed_checks": row["passed_checks"],
            "failed_checks": row["failed_checks"],
            "warning_checks": row["warning_checks"],
            "created_at": _iso(row["created_at"]),
            "completed_at": _iso(row["completed_at"]),
        }

    async def get_gate_check_results(self, package_id: str) -> list[dict]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT c.check_key, c.check_type, c.status, c.severity, c.blocking, "
                " c.evidence_ref, c.summary "
                "FROM acceptance_gate_check_results c "
                "JOIN acceptance_gate_runs g ON g.id = c.gate_run_id "
                "WHERE c.package_id = $1::uuid "
                "ORDER BY g.created_at DESC, c.created_at",
                package_id,
            )
        finally:
            await conn.close()
        return [
            {
                "check_key": r["check_key"],
                "check_type": r["check_type"],
                "status": r["status"],
                "severity": r["severity"],
                "blocking": r["blocking"],
                "evidence_ref": _dec(r["evidence_ref"], {}),
                "summary": r["summary"],
            }
            for r in rows
        ]

    async def get_handoff_summaries(self, package_id: str) -> list[dict]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT summary_type, title, summary, highlights, limitations, next_steps, "
                " artifact_refs, created_by_agent FROM handoff_summaries "
                "WHERE package_id = $1::uuid ORDER BY summary_type",
                package_id,
            )
        finally:
            await conn.close()
        return [
            {
                "summary_type": r["summary_type"],
                "title": r["title"],
                "summary": r["summary"],
                "highlights": _dec(r["highlights"], []),
                "limitations": _dec(r["limitations"], []),
                "next_steps": _dec(r["next_steps"], []),
                "artifact_refs": _dec(r["artifact_refs"], []),
                "created_by_agent": r["created_by_agent"],
            }
            for r in rows
        ]

    async def get_readiness_snapshot(self, package_id: str) -> dict | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT readiness_status, project_ready, design_ready, workspace_ready, qa_ready, "
                " acceptance_ready, safety_ready, docs_ready, human_acceptance_pending, "
                " blocking_reasons, warnings, created_at "
                "FROM delivery_readiness_snapshots WHERE package_id = $1::uuid "
                "ORDER BY created_at DESC LIMIT 1",
                package_id,
            )
        finally:
            await conn.close()
        if not row:
            return None
        return {
            "readiness_status": row["readiness_status"],
            "project_ready": row["project_ready"],
            "design_ready": row["design_ready"],
            "workspace_ready": row["workspace_ready"],
            "qa_ready": row["qa_ready"],
            "acceptance_ready": row["acceptance_ready"],
            "safety_ready": row["safety_ready"],
            "docs_ready": row["docs_ready"],
            "human_acceptance_pending": row["human_acceptance_pending"],
            "blocking_reasons": _dec(row["blocking_reasons"], []),
            "warnings": _dec(row["warnings"], []),
            "created_at": _iso(row["created_at"]),
        }

    async def get_operator_review(self, package_id: str) -> dict | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT id, reviewer, review_status, review_summary, requested_changes, "
                " reviewed_at, created_at FROM operator_acceptance_reviews "
                "WHERE package_id = $1::uuid ORDER BY created_at DESC LIMIT 1",
                package_id,
            )
        finally:
            await conn.close()
        if not row:
            return None
        return {
            "id": str(row["id"]),
            "reviewer": row["reviewer"],
            "review_status": row["review_status"],
            "review_summary": row["review_summary"],
            "requested_changes": _dec(row["requested_changes"], []),
            "reviewed_at": _iso(row["reviewed_at"]),
            "created_at": _iso(row["created_at"]),
        }

    async def get_delivery_package_report(self, package_id: str) -> dict | None:
        pkg = await self.get_delivery_package(package_id)
        if pkg is None:
            return None
        report = (pkg.get("metadata") or {}).get("report")
        return report if isinstance(report, dict) else None


__all__ = ["DeliveryPackageStore", "DEFAULT_DATABASE_URL"]
