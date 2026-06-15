"""Stage 47 -- asyncpg store for the controlled workspace operator tables.

Extends the Stage 28 ``code_workspaces`` table (additive columns) and writes
the six new Stage 47 tables. Short-lived connections, like the Stage 45/46
stores. ``task_id`` (Stage 28 NOT NULL) is set to the ``workspace_key``.
"""

from __future__ import annotations

import json
import os
from typing import Any

import asyncpg

from shared.sdk.observability.tracing import start_span
from shared.sdk.workspace_operator.models import (
    CodeWorkspace,
    WorkItemExecutionLink,
    WorkspaceArtifact,
    WorkspaceDiffSummary,
    WorkspaceFile,
    WorkspaceOperation,
    WorkspaceTestRun,
)

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


class WorkspaceOperatorStore:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.database_url, timeout=5)

    # ------------------------------------------------------------------ create
    async def create_workspace(self, ws: CodeWorkspace) -> str:
        with start_span("workspace_operator.create_workspace", **{"db.table": "code_workspaces"}):
            conn = await self._connect()
            try:
                row = await conn.fetchrow(
                    "INSERT INTO code_workspaces "
                    "(task_id, workspace_key, workspace_type, workspace_root, workspace_path, "
                    " status, generation_mode, generator_mode, project_id, "
                    " design_review_session_id, source_task_id, repo_write_enabled, "
                    " github_write_enabled, deployment_enabled, real_llm_enabled, "
                    " production_executed, created_by_agent, metadata) "
                    "VALUES ($1, $2, $3, $4, $4, $5, $6, $6, $7::uuid, $8::uuid, $9::uuid, "
                    " $10, $11, $12, $13, $14, $15, $16::jsonb) RETURNING workspace_id",
                    ws.workspace_key,
                    ws.workspace_key,
                    ws.workspace_type,
                    ws.workspace_root,
                    ws.status,
                    ws.generation_mode,
                    ws.project_id,
                    ws.design_review_session_id,
                    ws.source_task_id,
                    ws.repo_write_enabled,
                    ws.github_write_enabled,
                    ws.deployment_enabled,
                    ws.real_llm_enabled,
                    ws.production_executed,
                    ws.created_by_agent,
                    json.dumps(ws.metadata or {}),
                )
            finally:
                await conn.close()
            return str(row["workspace_id"])

    async def update_workspace_status(
        self, workspace_id: str, status: str, *, completed: bool = False
    ) -> None:
        conn = await self._connect()
        try:
            await conn.execute(
                "UPDATE code_workspaces SET status = $2, updated_at = now(), "
                " completed_at = CASE WHEN $3 THEN now() ELSE completed_at END "
                "WHERE workspace_id = $1::uuid",
                workspace_id,
                status,
                completed,
            )
        finally:
            await conn.close()

    async def record_workspace_file(
        self, workspace_id: str, f: WorkspaceFile, *, project_id: str | None = None
    ) -> str:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO workspace_files "
                "(workspace_id, project_id, relative_path, file_type, operation, "
                " content_hash, size_bytes, summary, metadata) "
                "VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8, $9::jsonb) RETURNING id",
                workspace_id,
                project_id,
                f.relative_path,
                f.file_type,
                f.operation,
                f.content_hash,
                f.size_bytes,
                f.summary,
                json.dumps(f.metadata or {}),
            )
        finally:
            await conn.close()
        return str(row["id"])

    async def record_workspace_files(
        self, workspace_id: str, files: list[WorkspaceFile], *, project_id: str | None = None
    ) -> int:
        if not files:
            return 0
        conn = await self._connect()
        try:
            async with conn.transaction():
                for f in files:
                    await conn.execute(
                        "INSERT INTO workspace_files "
                        "(workspace_id, project_id, relative_path, file_type, operation, "
                        " content_hash, size_bytes, summary, metadata) "
                        "VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8, $9::jsonb)",
                        workspace_id,
                        project_id,
                        f.relative_path,
                        f.file_type,
                        f.operation,
                        f.content_hash,
                        f.size_bytes,
                        f.summary,
                        json.dumps(f.metadata or {}),
                    )
        finally:
            await conn.close()
        return len(files)

    async def record_operation(
        self, workspace_id: str, op: WorkspaceOperation, *, project_id: str | None = None
    ) -> str:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO workspace_operations "
                "(workspace_id, project_id, operation_type, status, command, exit_code, "
                " completed_at, output_summary, metadata) "
                "VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, now(), $7, $8::jsonb) RETURNING id",
                workspace_id,
                project_id,
                op.operation_type,
                op.status,
                op.command,
                op.exit_code,
                op.output_summary,
                json.dumps(op.metadata or {}),
            )
        finally:
            await conn.close()
        return str(row["id"])

    async def record_test_run(
        self, workspace_id: str, run: WorkspaceTestRun, *, project_id: str | None = None
    ) -> str:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO workspace_test_runs "
                "(workspace_id, project_id, test_type, command, status, exit_code, "
                " tests_total, tests_passed, tests_failed, duration_ms, output_summary, "
                " report_path, metadata) "
                "VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13::jsonb) "
                "RETURNING id",
                workspace_id,
                project_id,
                run.test_type,
                run.command,
                run.status,
                run.exit_code,
                run.tests_total,
                run.tests_passed,
                run.tests_failed,
                run.duration_ms,
                run.output_summary,
                run.report_path,
                json.dumps(run.metadata or {}),
            )
        finally:
            await conn.close()
        return str(row["id"])

    async def record_diff_summary(
        self, workspace_id: str, diff: WorkspaceDiffSummary, *, project_id: str | None = None
    ) -> str:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO workspace_diff_summaries "
                "(workspace_id, project_id, changed_files_count, created_files_count, "
                " modified_files_count, deleted_files_count, diff_summary, risk_summary, "
                " test_summary, metadata) "
                "VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7::jsonb, $8, $9, $10::jsonb) "
                "RETURNING id",
                workspace_id,
                project_id,
                diff.changed_files_count,
                diff.created_files_count,
                diff.modified_files_count,
                diff.deleted_files_count,
                json.dumps(diff.diff_summary or {}),
                diff.risk_summary,
                diff.test_summary,
                json.dumps(diff.metadata or {}),
            )
        finally:
            await conn.close()
        return str(row["id"])

    async def record_artifact(
        self, workspace_id: str, artifact: WorkspaceArtifact, *, project_id: str | None = None
    ) -> str:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO workspace_artifacts "
                "(workspace_id, project_id, artifact_type, title, content, uri, "
                " created_by_agent, metadata) "
                "VALUES ($1::uuid, $2::uuid, $3, $4, $5::jsonb, $6, $7, $8::jsonb) RETURNING id",
                workspace_id,
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

    async def link_work_item_execution(
        self,
        project_id: str,
        workspace_id: str,
        link: WorkItemExecutionLink,
    ) -> str:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO work_item_execution_links "
                "(project_id, work_item_id, workspace_id, execution_status, "
                " evidence_artifact_id, metadata) "
                "VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5::uuid, $6::jsonb) "
                "ON CONFLICT (work_item_id, workspace_id) DO UPDATE SET "
                " execution_status = EXCLUDED.execution_status, "
                " evidence_artifact_id = EXCLUDED.evidence_artifact_id, updated_at = now() "
                "RETURNING id",
                project_id,
                link.work_item_id,
                workspace_id,
                link.execution_status,
                link.evidence_artifact_id,
                json.dumps({**(link.metadata or {}), "work_item_key": link.work_item_key}),
            )
        finally:
            await conn.close()
        return str(row["id"])

    # -------------------------------------------------------------------- reads
    @staticmethod
    def _workspace_row(r: asyncpg.Record) -> dict:
        return {
            "workspace_id": str(r["workspace_id"]),
            "workspace_key": r["workspace_key"],
            "workspace_type": r["workspace_type"],
            "workspace_root": r["workspace_root"],
            "status": r["status"],
            "generation_mode": r["generation_mode"],
            "project_id": str(r["project_id"]) if r["project_id"] else None,
            "design_review_session_id": (
                str(r["design_review_session_id"]) if r["design_review_session_id"] else None
            ),
            "repo_write_enabled": r["repo_write_enabled"],
            "github_write_enabled": r["github_write_enabled"],
            "deployment_enabled": r["deployment_enabled"],
            "real_llm_enabled": r["real_llm_enabled"],
            "production_executed": r["production_executed"],
            "created_by_agent": r["created_by_agent"],
            "created_at": _iso(r["created_at"]),
            "completed_at": _iso(r["completed_at"]),
            "metadata": _dec(r["metadata"], {}),
        }

    _WS_COLS = (
        "workspace_id, workspace_key, workspace_type, workspace_root, status, generation_mode, "
        "project_id, design_review_session_id, repo_write_enabled, github_write_enabled, "
        "deployment_enabled, real_llm_enabled, production_executed, created_by_agent, "
        "created_at, completed_at, metadata"
    )

    async def get_workspace(self, workspace_id: str) -> dict | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                f"SELECT {self._WS_COLS} FROM code_workspaces WHERE workspace_id = $1::uuid",
                workspace_id,
            )
        except (asyncpg.PostgresError, ValueError):
            row = None
        finally:
            await conn.close()
        return self._workspace_row(row) if row else None

    async def list_workspaces(
        self, *, project_id: str | None = None, limit: int = 100
    ) -> list[dict]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                f"SELECT {self._WS_COLS} FROM code_workspaces "
                "WHERE workspace_key IS NOT NULL "
                "AND ($1::uuid IS NULL OR project_id = $1::uuid) "
                "ORDER BY created_at DESC LIMIT $2",
                project_id,
                max(1, min(int(limit), 500)),
            )
        finally:
            await conn.close()
        return [self._workspace_row(r) for r in rows]

    async def get_latest_workspace(self, project_id: str | None = None) -> dict | None:
        rows = await self.list_workspaces(project_id=project_id, limit=1)
        return rows[0] if rows else None

    async def list_workspace_files(self, workspace_id: str) -> list[dict]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT relative_path, file_type, operation, content_hash, size_bytes, summary "
                "FROM workspace_files WHERE workspace_id = $1::uuid ORDER BY relative_path",
                workspace_id,
            )
        finally:
            await conn.close()
        return [dict(r) for r in rows]

    async def list_operations(self, workspace_id: str) -> list[dict]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT operation_type, status, command, exit_code, output_summary, "
                " started_at, completed_at FROM workspace_operations "
                "WHERE workspace_id = $1::uuid ORDER BY started_at",
                workspace_id,
            )
        finally:
            await conn.close()
        return [
            {
                "operation_type": r["operation_type"],
                "status": r["status"],
                "command": r["command"],
                "exit_code": r["exit_code"],
                "output_summary": r["output_summary"],
                "started_at": _iso(r["started_at"]),
                "completed_at": _iso(r["completed_at"]),
            }
            for r in rows
        ]

    async def list_test_runs(self, workspace_id: str) -> list[dict]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT test_type, command, status, exit_code, tests_total, tests_passed, "
                " tests_failed, duration_ms, output_summary, report_path FROM workspace_test_runs "
                "WHERE workspace_id = $1::uuid ORDER BY created_at",
                workspace_id,
            )
        finally:
            await conn.close()
        return [dict(r) for r in rows]

    async def get_diff_summary(self, workspace_id: str) -> dict | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT id, changed_files_count, created_files_count, modified_files_count, "
                " deleted_files_count, diff_summary, risk_summary, test_summary, generated_at "
                "FROM workspace_diff_summaries WHERE workspace_id = $1::uuid "
                "ORDER BY generated_at DESC LIMIT 1",
                workspace_id,
            )
        finally:
            await conn.close()
        if not row:
            return None
        return {
            "id": str(row["id"]),
            "changed_files_count": row["changed_files_count"],
            "created_files_count": row["created_files_count"],
            "modified_files_count": row["modified_files_count"],
            "deleted_files_count": row["deleted_files_count"],
            "diff_summary": _dec(row["diff_summary"], {}),
            "risk_summary": row["risk_summary"],
            "test_summary": row["test_summary"],
            "generated_at": _iso(row["generated_at"]),
        }

    async def list_artifacts(self, workspace_id: str) -> list[dict]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT artifact_type, title, uri, created_by_agent, created_at "
                "FROM workspace_artifacts WHERE workspace_id = $1::uuid ORDER BY created_at",
                workspace_id,
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

    async def list_work_item_links(self, project_id: str) -> list[dict]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT work_item_id, workspace_id, execution_status, evidence_artifact_id, "
                " metadata FROM work_item_execution_links WHERE project_id = $1::uuid "
                "ORDER BY created_at",
                project_id,
            )
        finally:
            await conn.close()
        return [
            {
                "work_item_id": str(r["work_item_id"]),
                "workspace_id": str(r["workspace_id"]),
                "execution_status": r["execution_status"],
                "evidence_artifact_id": (
                    str(r["evidence_artifact_id"]) if r["evidence_artifact_id"] else None
                ),
                "work_item_key": _dec(r["metadata"], {}).get("work_item_key"),
            }
            for r in rows
        ]

    async def get_workspace_report(self, workspace_id: str) -> dict:
        ws = await self.get_workspace(workspace_id)
        files = await self.list_workspace_files(workspace_id)
        tests = await self.list_test_runs(workspace_id)
        diff = await self.get_diff_summary(workspace_id)
        artifacts = await self.list_artifacts(workspace_id)
        links: list[dict] = []
        if ws and ws.get("project_id"):
            all_links = await self.list_work_item_links(ws["project_id"])
            links = [link for link in all_links if link["workspace_id"] == workspace_id]
        return {
            "workspace": ws,
            "files": files,
            "files_count": len(files),
            "test_runs": tests,
            "diff_summary": diff,
            "artifacts": artifacts,
            "work_item_links": links,
            "production_executed": False,
        }

    async def compute_workspace_summary(self, project_id: str) -> dict:
        ws = await self.get_latest_workspace(project_id)
        if not ws:
            return {
                "project_id": project_id,
                "latest_workspace_id": None,
                "latest_workspace_status": None,
                "production_executed": False,
            }
        tests = await self.list_test_runs(ws["workspace_id"])
        diff = await self.get_diff_summary(ws["workspace_id"])
        files = await self.list_workspace_files(ws["workspace_id"])
        pytest_run = next((t for t in tests if t["test_type"] == "pytest"), None)
        static_runs = [t for t in tests if t["test_type"] in ("ruff", "compileall", "static_check")]
        static_status: str | None = "passed"
        if any(t["status"] == "failed" for t in static_runs):
            static_status = "failed"
        elif not static_runs:
            static_status = None
        return {
            "project_id": project_id,
            "latest_workspace_id": ws["workspace_id"],
            "latest_workspace_status": ws["status"],
            "latest_workspace_tests_status": pytest_run["status"] if pytest_run else None,
            "latest_workspace_static_check_status": static_status,
            "latest_workspace_generated_files_count": len(files),
            "diff_summary_id": diff["id"] if diff else None,
            "production_executed": False,
        }


__all__ = ["WorkspaceOperatorStore", "DEFAULT_DATABASE_URL"]
