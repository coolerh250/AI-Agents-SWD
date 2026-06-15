"""Stage 48 -- asyncpg store for the mini delivery pilot tables."""

from __future__ import annotations

import json
import os
from typing import Any

import asyncpg

from shared.sdk.mini_delivery_pilot.models import (
    AcceptanceEvaluation,
    MiniDeliveryPilot,
    MiniDeliveryPilotStep,
    MiniDeliveryReport,
    PilotArtifact,
    QAEvidenceReport,
    SafetyEvidenceReport,
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


class MiniDeliveryPilotStore:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.database_url, timeout=5)

    # ------------------------------------------------------------------ create
    async def create_pilot(self, pilot: MiniDeliveryPilot) -> str:
        with start_span("mini_delivery.create_pilot", **{"db.table": "mini_delivery_pilots"}):
            conn = await self._connect()
            try:
                row = await conn.fetchrow(
                    "INSERT INTO mini_delivery_pilots "
                    "(project_id, source_task_id, workspace_id, design_review_session_id, "
                    " graph_snapshot_id, pilot_key, pilot_type, status, controlled_only, "
                    " created_by_agent, metadata) "
                    "VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5::uuid, $6, $7, $8, $9, "
                    " $10, $11::jsonb) RETURNING id",
                    pilot.project_id,
                    pilot.source_task_id,
                    pilot.workspace_id,
                    pilot.design_review_session_id,
                    pilot.graph_snapshot_id,
                    pilot.pilot_key,
                    pilot.pilot_type,
                    pilot.status,
                    pilot.controlled_only,
                    pilot.created_by_agent,
                    json.dumps(pilot.metadata or {}),
                )
            finally:
                await conn.close()
            return str(row["id"])

    async def update_pilot_status(
        self,
        pilot_id: str,
        status: str,
        *,
        completed: bool = False,
        project_id: str | None = None,
        workspace_id: str | None = None,
        design_review_session_id: str | None = None,
        graph_snapshot_id: str | None = None,
    ) -> None:
        conn = await self._connect()
        try:
            await conn.execute(
                "UPDATE mini_delivery_pilots SET status = $2, updated_at = now(), "
                " completed_at = CASE WHEN $3 THEN now() ELSE completed_at END, "
                " project_id = COALESCE($4::uuid, project_id), "
                " workspace_id = COALESCE($5::uuid, workspace_id), "
                " design_review_session_id = COALESCE($6::uuid, design_review_session_id), "
                " graph_snapshot_id = COALESCE($7::uuid, graph_snapshot_id) "
                "WHERE id = $1::uuid",
                pilot_id,
                status,
                completed,
                project_id,
                workspace_id,
                design_review_session_id,
                graph_snapshot_id,
            )
        finally:
            await conn.close()

    async def create_step(
        self, pilot_id: str, step: MiniDeliveryPilotStep, *, project_id: str | None = None
    ) -> str:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO mini_delivery_pilot_steps "
                "(pilot_id, project_id, step_key, step_type, status, completed_at, "
                " evidence_refs, summary, metadata) "
                "VALUES ($1::uuid, $2::uuid, $3, $4, $5, now(), $6::jsonb, $7, $8::jsonb) "
                "RETURNING id",
                pilot_id,
                project_id,
                step.step_key,
                step.step_type,
                step.status,
                json.dumps(step.evidence_refs or []),
                step.summary,
                json.dumps(step.metadata or {}),
            )
        finally:
            await conn.close()
        return str(row["id"])

    async def create_acceptance_evaluations(
        self, pilot_id: str, project_id: str | None, evaluations: list[AcceptanceEvaluation]
    ) -> int:
        if not evaluations:
            return 0
        conn = await self._connect()
        try:
            async with conn.transaction():
                for e in evaluations:
                    await conn.execute(
                        "INSERT INTO acceptance_evaluations "
                        "(pilot_id, project_id, acceptance_criterion_id, work_item_id, "
                        " evaluation_status, evidence_type, evidence_ref, evaluator, "
                        " rationale_summary, metadata) "
                        "VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6, $7::jsonb, $8, "
                        " $9, $10::jsonb) "
                        "ON CONFLICT (pilot_id, acceptance_criterion_id) DO UPDATE SET "
                        " evaluation_status = EXCLUDED.evaluation_status, "
                        " evidence_type = EXCLUDED.evidence_type, "
                        " evidence_ref = EXCLUDED.evidence_ref, "
                        " rationale_summary = EXCLUDED.rationale_summary",
                        pilot_id,
                        project_id,
                        e.acceptance_criterion_id,
                        e.work_item_id,
                        e.evaluation_status,
                        e.evidence_type,
                        json.dumps(e.evidence_ref or {}),
                        e.evaluator,
                        e.rationale_summary,
                        json.dumps({**(e.metadata or {}), "criterion_key": e.criterion_key}),
                    )
        finally:
            await conn.close()
        return len(evaluations)

    async def create_qa_report(
        self, pilot_id: str, project_id: str | None, workspace_id: str | None, qa: QAEvidenceReport
    ) -> str:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO qa_evidence_reports "
                "(pilot_id, project_id, workspace_id, status, tests_total, tests_passed, "
                " tests_failed, static_checks_status, coverage_summary, findings, "
                " report_summary, created_by_agent, metadata) "
                "VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7, $8, $9::jsonb, $10::jsonb, "
                " $11, $12, $13::jsonb) RETURNING id",
                pilot_id,
                project_id,
                workspace_id,
                qa.status,
                qa.tests_total,
                qa.tests_passed,
                qa.tests_failed,
                qa.static_checks_status,
                json.dumps(qa.coverage_summary or {}),
                json.dumps(qa.findings or []),
                qa.report_summary,
                qa.created_by_agent,
                json.dumps(qa.metadata or {}),
            )
        finally:
            await conn.close()
        return str(row["id"])

    async def create_safety_report(
        self,
        pilot_id: str,
        project_id: str | None,
        workspace_id: str | None,
        safety: SafetyEvidenceReport,
    ) -> str:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO safety_evidence_reports "
                "(pilot_id, project_id, workspace_id, status, production_executed_count, "
                " github_write_performed, pr_created, deployment_performed, real_llm_used, "
                " real_external_delivery_performed, repo_root_modified, secret_leak_detected, "
                " chain_of_thought_persisted, findings, report_summary, created_by_agent, metadata) "
                "VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, "
                " $14::jsonb, $15, $16, $17::jsonb) RETURNING id",
                pilot_id,
                project_id,
                workspace_id,
                safety.status,
                safety.production_executed_count,
                safety.github_write_performed,
                safety.pr_created,
                safety.deployment_performed,
                safety.real_llm_used,
                safety.real_external_delivery_performed,
                safety.repo_root_modified,
                safety.secret_leak_detected,
                safety.chain_of_thought_persisted,
                json.dumps(safety.findings or []),
                safety.report_summary,
                safety.created_by_agent,
                json.dumps(safety.metadata or {}),
            )
        finally:
            await conn.close()
        return str(row["id"])

    async def create_delivery_report(
        self,
        pilot_id: str,
        project_id: str | None,
        workspace_id: str | None,
        report: MiniDeliveryReport,
    ) -> str:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO mini_delivery_reports "
                "(pilot_id, project_id, workspace_id, report_type, status, title, "
                " executive_summary, project_summary, design_review_summary, workspace_summary, "
                " qa_summary, acceptance_summary, safety_summary, known_limitations, next_steps, "
                " artifact_refs, created_by_agent, metadata) "
                "VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7, $8::jsonb, $9::jsonb, "
                " $10::jsonb, $11::jsonb, $12::jsonb, $13::jsonb, $14::jsonb, $15::jsonb, "
                " $16::jsonb, $17, $18::jsonb) RETURNING id",
                pilot_id,
                project_id,
                workspace_id,
                report.report_type,
                report.status,
                report.title,
                report.executive_summary,
                json.dumps(report.project_summary or {}),
                json.dumps(report.design_review_summary or {}),
                json.dumps(report.workspace_summary or {}),
                json.dumps(report.qa_summary or {}),
                json.dumps(report.acceptance_summary or {}),
                json.dumps(report.safety_summary or {}),
                json.dumps(report.known_limitations or []),
                json.dumps(report.next_steps or []),
                json.dumps(report.artifact_refs or []),
                report.created_by_agent,
                json.dumps(report.metadata or {}),
            )
        finally:
            await conn.close()
        return str(row["id"])

    async def create_pilot_artifact(
        self, pilot_id: str, project_id: str | None, artifact: PilotArtifact
    ) -> str:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO pilot_artifacts "
                "(pilot_id, project_id, artifact_type, title, content, uri, created_by_agent, "
                " metadata) "
                "VALUES ($1::uuid, $2::uuid, $3, $4, $5::jsonb, $6, $7, $8::jsonb) RETURNING id",
                pilot_id,
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

    # -------------------------------------------------------------------- reads
    @staticmethod
    def _pilot_row(r: asyncpg.Record) -> dict:
        return {
            "id": str(r["id"]),
            "pilot_key": r["pilot_key"],
            "pilot_type": r["pilot_type"],
            "status": r["status"],
            "project_id": str(r["project_id"]) if r["project_id"] else None,
            "workspace_id": str(r["workspace_id"]) if r["workspace_id"] else None,
            "design_review_session_id": (
                str(r["design_review_session_id"]) if r["design_review_session_id"] else None
            ),
            "controlled_only": r["controlled_only"],
            "production_executed": r["production_executed"],
            "created_by_agent": r["created_by_agent"],
            "created_at": _iso(r["created_at"]),
            "completed_at": _iso(r["completed_at"]),
            "metadata": _dec(r["metadata"], {}),
        }

    _PILOT_COLS = (
        "id, pilot_key, pilot_type, status, project_id, workspace_id, "
        "design_review_session_id, controlled_only, production_executed, created_by_agent, "
        "created_at, completed_at, metadata"
    )

    async def get_pilot(self, pilot_id: str) -> dict | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                f"SELECT {self._PILOT_COLS} FROM mini_delivery_pilots WHERE id = $1::uuid",
                pilot_id,
            )
        except (asyncpg.PostgresError, ValueError):
            row = None
        finally:
            await conn.close()
        return self._pilot_row(row) if row else None

    async def list_pilots(self, *, project_id: str | None = None, limit: int = 100) -> list[dict]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                f"SELECT {self._PILOT_COLS} FROM mini_delivery_pilots "
                "WHERE ($1::uuid IS NULL OR project_id = $1::uuid) "
                "ORDER BY created_at DESC LIMIT $2",
                project_id,
                max(1, min(int(limit), 500)),
            )
        finally:
            await conn.close()
        return [self._pilot_row(r) for r in rows]

    async def get_latest_pilot(self, project_id: str | None = None) -> dict | None:
        rows = await self.list_pilots(project_id=project_id, limit=1)
        return rows[0] if rows else None

    async def list_steps(self, pilot_id: str) -> list[dict]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT step_key, step_type, status, evidence_refs, summary, started_at, "
                " completed_at FROM mini_delivery_pilot_steps WHERE pilot_id = $1::uuid "
                "ORDER BY started_at",
                pilot_id,
            )
        finally:
            await conn.close()
        return [
            {
                "step_key": r["step_key"],
                "step_type": r["step_type"],
                "status": r["status"],
                "evidence_refs": _dec(r["evidence_refs"], []),
                "summary": r["summary"],
                "started_at": _iso(r["started_at"]),
                "completed_at": _iso(r["completed_at"]),
            }
            for r in rows
        ]

    async def list_acceptance_evaluations(self, pilot_id: str) -> list[dict]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT acceptance_criterion_id, work_item_id, evaluation_status, evidence_type, "
                " evidence_ref, rationale_summary, metadata FROM acceptance_evaluations "
                "WHERE pilot_id = $1::uuid ORDER BY created_at",
                pilot_id,
            )
        finally:
            await conn.close()
        return [
            {
                "acceptance_criterion_id": (
                    str(r["acceptance_criterion_id"]) if r["acceptance_criterion_id"] else None
                ),
                "work_item_id": str(r["work_item_id"]) if r["work_item_id"] else None,
                "evaluation_status": r["evaluation_status"],
                "evidence_type": r["evidence_type"],
                "evidence_ref": _dec(r["evidence_ref"], {}),
                "rationale_summary": r["rationale_summary"],
                "criterion_key": _dec(r["metadata"], {}).get("criterion_key"),
            }
            for r in rows
        ]

    async def get_acceptance_summary(self, pilot_id: str) -> dict:
        rows = await self.list_acceptance_evaluations(pilot_id)
        return {
            "total": len(rows),
            "satisfied": sum(1 for r in rows if r["evaluation_status"] == "satisfied"),
            "failed": sum(1 for r in rows if r["evaluation_status"] == "failed"),
            "pending": sum(1 for r in rows if r["evaluation_status"] == "pending"),
            "waived": sum(1 for r in rows if r["evaluation_status"] == "waived"),
        }

    async def _get_one(self, table: str, pilot_id: str, cols: str) -> dict | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                f"SELECT {cols} FROM {table} WHERE pilot_id = $1::uuid "
                "ORDER BY created_at DESC LIMIT 1",
                pilot_id,
            )
        finally:
            await conn.close()
        return dict(row) if row else None

    async def get_qa_report(self, pilot_id: str) -> dict | None:
        return await self._get_one(
            "qa_evidence_reports",
            pilot_id,
            "status, tests_total, tests_passed, tests_failed, static_checks_status, "
            "findings, report_summary",
        )

    async def get_safety_report(self, pilot_id: str) -> dict | None:
        return await self._get_one(
            "safety_evidence_reports",
            pilot_id,
            "status, production_executed_count, github_write_performed, pr_created, "
            "deployment_performed, real_llm_used, real_external_delivery_performed, "
            "repo_root_modified, secret_leak_detected, chain_of_thought_persisted, "
            "findings, report_summary",
        )

    async def get_pilot_report(self, pilot_id: str) -> dict | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT report_type, status, title, executive_summary, project_summary, "
                " design_review_summary, workspace_summary, qa_summary, acceptance_summary, "
                " safety_summary, known_limitations, next_steps, artifact_refs "
                "FROM mini_delivery_reports WHERE pilot_id = $1::uuid "
                "ORDER BY created_at DESC LIMIT 1",
                pilot_id,
            )
        finally:
            await conn.close()
        if not row:
            return None
        return {
            "report_type": row["report_type"],
            "status": row["status"],
            "title": row["title"],
            "executive_summary": row["executive_summary"],
            "project_summary": _dec(row["project_summary"], {}),
            "design_review_summary": _dec(row["design_review_summary"], {}),
            "workspace_summary": _dec(row["workspace_summary"], {}),
            "qa_summary": _dec(row["qa_summary"], {}),
            "acceptance_summary": _dec(row["acceptance_summary"], {}),
            "safety_summary": _dec(row["safety_summary"], {}),
            "known_limitations": _dec(row["known_limitations"], []),
            "next_steps": _dec(row["next_steps"], []),
            "artifact_refs": _dec(row["artifact_refs"], []),
        }

    async def list_artifacts(self, pilot_id: str) -> list[dict]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT artifact_type, title, uri, created_by_agent, created_at "
                "FROM pilot_artifacts WHERE pilot_id = $1::uuid ORDER BY created_at",
                pilot_id,
            )
        finally:
            await conn.close()
        return [
            {
                "artifact_type": r["artifact_type"],
                "title": r["title"],
                "uri": r["uri"],
                "created_by_agent": r["created_by_agent"],
                "created_at": _iso(r["created_at"]),
            }
            for r in rows
        ]

    async def get_pilot_timeline(self, pilot_id: str) -> dict:
        pilot = await self.get_pilot(pilot_id)
        steps = await self.list_steps(pilot_id)
        return {
            "pilot": pilot,
            "steps": steps,
            "step_count": len(steps),
            "production_executed": False,
        }


__all__ = ["MiniDeliveryPilotStore", "DEFAULT_DATABASE_URL"]
