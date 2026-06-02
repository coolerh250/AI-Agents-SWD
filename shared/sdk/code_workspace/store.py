"""asyncpg store for the Stage 28 code-generation workspace tables."""

from __future__ import annotations

import json
import os
from typing import Any

import asyncpg

from shared.sdk.code_workspace.models import (
    CodeChangeArtifact,
    CodeWorkspace,
    PRDraftArtifact,
)
from shared.sdk.observability.tracing import start_span

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"

_WORKSPACE_COLUMNS = (
    "workspace_id, task_id, workflow_id, work_item_id, execution_mode, status, "
    "base_commit, branch_name, workspace_path, allowed_paths, denied_paths, "
    "generator_mode, blocked_reason, created_by_agent, created_at, updated_at"
)

_ARTIFACT_COLUMNS = (
    "artifact_id, task_id, workflow_id, workspace_id, file_path, change_type, "
    "before_sha, after_sha, diff_summary, diff_text, generated_content_preview, "
    "validation_status, created_at"
)

_PR_DRAFT_COLUMNS = (
    "pr_draft_id, task_id, workflow_id, workspace_id, title, body, "
    "changed_files, test_results, risk_assessment, rollback_plan, "
    "github_dry_run_result, status, created_at"
)


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _decode_json(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return fallback
    return value


def _row_to_workspace(row: asyncpg.Record) -> CodeWorkspace:
    return CodeWorkspace(
        workspace_id=str(row["workspace_id"]),
        task_id=row["task_id"],
        workflow_id=row["workflow_id"],
        work_item_id=str(row["work_item_id"]) if row["work_item_id"] is not None else None,
        execution_mode=row["execution_mode"] or "simple_task",
        status=row["status"] or "created",
        base_commit=row["base_commit"] or "",
        branch_name=row["branch_name"] or "",
        workspace_path=row["workspace_path"] or "",
        allowed_paths=_decode_json(row["allowed_paths"], []) or [],
        denied_paths=_decode_json(row["denied_paths"], []) or [],
        generator_mode=row["generator_mode"] or "deterministic_template",
        blocked_reason=row["blocked_reason"] or "",
        created_by_agent=row["created_by_agent"] or "development-agent",
        created_at=_iso(row["created_at"]),
        updated_at=_iso(row["updated_at"]),
    )


def _row_to_artifact(row: asyncpg.Record) -> CodeChangeArtifact:
    return CodeChangeArtifact(
        artifact_id=str(row["artifact_id"]),
        task_id=row["task_id"],
        workflow_id=row["workflow_id"],
        workspace_id=str(row["workspace_id"]),
        file_path=row["file_path"],
        change_type=row["change_type"] or "create",
        before_sha=row["before_sha"],
        after_sha=row["after_sha"],
        diff_summary=row["diff_summary"] or "",
        diff_text=row["diff_text"] or "",
        generated_content_preview=row["generated_content_preview"] or "",
        validation_status=row["validation_status"] or "pending",
        created_at=_iso(row["created_at"]),
    )


def _row_to_pr_draft(row: asyncpg.Record) -> PRDraftArtifact:
    return PRDraftArtifact(
        pr_draft_id=str(row["pr_draft_id"]),
        task_id=row["task_id"],
        workflow_id=row["workflow_id"],
        workspace_id=str(row["workspace_id"]),
        title=row["title"] or "",
        body=row["body"] or "",
        changed_files=_decode_json(row["changed_files"], []) or [],
        test_results=_decode_json(row["test_results"], {}) or {},
        risk_assessment=_decode_json(row["risk_assessment"], {}) or {},
        rollback_plan=row["rollback_plan"] or "",
        github_dry_run_result=_decode_json(row["github_dry_run_result"], {}) or {},
        status=row["status"] or "draft",
        created_at=_iso(row["created_at"]),
    )


class CodeWorkspaceStore:
    """Wraps the three Stage 28 tables.

    Connection-per-call pattern (matches ``TaskExecutionStore`` and
    ``AuditStore``). ``DATABASE_URL`` drives the dsn; defaults to the
    local/test cluster's trust-auth postgres for the test fixtures.
    """

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.database_url, timeout=5)

    # ------------------------------------------------------------------
    # code_workspaces
    # ------------------------------------------------------------------

    async def create_workspace(
        self,
        *,
        task_id: str,
        workflow_id: str | None = None,
        work_item_id: str | None = None,
        execution_mode: str = "simple_task",
        status: str = "created",
        base_commit: str = "",
        branch_name: str = "",
        workspace_path: str = "",
        allowed_paths: list[str] | None = None,
        denied_paths: list[str] | None = None,
        generator_mode: str = "deterministic_template",
        blocked_reason: str = "",
        created_by_agent: str = "development-agent",
    ) -> CodeWorkspace:
        """Upsert one workspace by ``task_id``."""
        with start_span(
            "code_workspace.create",
            **{
                "db.table": "code_workspaces",
                "task_id": task_id,
                "workflow_id": workflow_id or "",
                "execution_mode": execution_mode,
                "status": status,
                "generator_mode": generator_mode,
            },
        ):
            conn = await self._connect()
            try:
                row = await conn.fetchrow(
                    "INSERT INTO code_workspaces "
                    "(task_id, workflow_id, work_item_id, execution_mode, status, "
                    " base_commit, branch_name, workspace_path, allowed_paths, "
                    " denied_paths, generator_mode, blocked_reason, created_by_agent) "
                    "VALUES ($1, $2, $3::uuid, $4, $5, $6, $7, $8, $9::jsonb, "
                    " $10::jsonb, $11, $12, $13) "
                    "ON CONFLICT (task_id) DO UPDATE SET "
                    " workflow_id = EXCLUDED.workflow_id, "
                    " work_item_id = EXCLUDED.work_item_id, "
                    " execution_mode = EXCLUDED.execution_mode, "
                    " status = EXCLUDED.status, "
                    " base_commit = EXCLUDED.base_commit, "
                    " branch_name = EXCLUDED.branch_name, "
                    " workspace_path = EXCLUDED.workspace_path, "
                    " allowed_paths = EXCLUDED.allowed_paths, "
                    " denied_paths = EXCLUDED.denied_paths, "
                    " generator_mode = EXCLUDED.generator_mode, "
                    " blocked_reason = EXCLUDED.blocked_reason, "
                    " created_by_agent = EXCLUDED.created_by_agent, "
                    " updated_at = now() "
                    f"RETURNING {_WORKSPACE_COLUMNS}",
                    task_id,
                    workflow_id,
                    work_item_id,
                    execution_mode,
                    status,
                    base_commit,
                    branch_name,
                    workspace_path,
                    json.dumps(allowed_paths or []),
                    json.dumps(denied_paths or []),
                    generator_mode,
                    blocked_reason,
                    created_by_agent,
                )
            finally:
                await conn.close()
            return _row_to_workspace(row)

    async def get_workspace(self, task_id: str) -> CodeWorkspace | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                f"SELECT {_WORKSPACE_COLUMNS} FROM code_workspaces WHERE task_id = $1",
                task_id,
            )
        finally:
            await conn.close()
        return _row_to_workspace(row) if row else None

    async def list_workspaces(
        self,
        *,
        status: str | None = None,
        generator_mode: str | None = None,
        limit: int = 100,
    ) -> list[CodeWorkspace]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                f"SELECT {_WORKSPACE_COLUMNS} FROM code_workspaces "
                "WHERE ($1::text IS NULL OR status = $1) "
                "AND ($2::text IS NULL OR generator_mode = $2) "
                "ORDER BY created_at DESC LIMIT $3",
                status,
                generator_mode,
                limit,
            )
        finally:
            await conn.close()
        return [_row_to_workspace(r) for r in rows]

    async def update_workspace_status(
        self,
        task_id: str,
        status: str,
        *,
        blocked_reason: str | None = None,
    ) -> CodeWorkspace | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "UPDATE code_workspaces SET status = $2, "
                " blocked_reason = COALESCE($3, blocked_reason), "
                " updated_at = now() "
                f"WHERE task_id = $1 RETURNING {_WORKSPACE_COLUMNS}",
                task_id,
                status,
                blocked_reason,
            )
        finally:
            await conn.close()
        return _row_to_workspace(row) if row else None

    # ------------------------------------------------------------------
    # code_change_artifacts
    # ------------------------------------------------------------------

    async def add_code_change_artifact(
        self,
        *,
        task_id: str,
        workflow_id: str | None,
        workspace_id: str,
        file_path: str,
        change_type: str = "create",
        before_sha: str | None = None,
        after_sha: str | None = None,
        diff_summary: str = "",
        diff_text: str = "",
        generated_content_preview: str = "",
        validation_status: str = "pending",
    ) -> CodeChangeArtifact:
        with start_span(
            "code_workspace.add_artifact",
            **{
                "db.table": "code_change_artifacts",
                "task_id": task_id,
                "workflow_id": workflow_id or "",
                "workspace_id": workspace_id,
                "file_path": file_path,
                "change_type": change_type,
            },
        ):
            conn = await self._connect()
            try:
                row = await conn.fetchrow(
                    "INSERT INTO code_change_artifacts "
                    "(task_id, workflow_id, workspace_id, file_path, change_type, "
                    " before_sha, after_sha, diff_summary, diff_text, "
                    " generated_content_preview, validation_status) "
                    "VALUES ($1, $2, $3::uuid, $4, $5, $6, $7, $8, $9, $10, $11) "
                    f"RETURNING {_ARTIFACT_COLUMNS}",
                    task_id,
                    workflow_id,
                    workspace_id,
                    file_path,
                    change_type,
                    before_sha,
                    after_sha,
                    diff_summary,
                    diff_text,
                    generated_content_preview,
                    validation_status,
                )
            finally:
                await conn.close()
            return _row_to_artifact(row)

    async def list_code_change_artifacts(self, task_id: str) -> list[CodeChangeArtifact]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                f"SELECT {_ARTIFACT_COLUMNS} FROM code_change_artifacts "
                "WHERE task_id = $1 ORDER BY created_at ASC",
                task_id,
            )
        finally:
            await conn.close()
        return [_row_to_artifact(r) for r in rows]

    # ------------------------------------------------------------------
    # pr_draft_artifacts
    # ------------------------------------------------------------------

    async def create_pr_draft_artifact(
        self,
        *,
        task_id: str,
        workflow_id: str | None,
        workspace_id: str,
        title: str,
        body: str,
        changed_files: list[Any],
        test_results: dict[str, Any] | None = None,
        risk_assessment: dict[str, Any] | None = None,
        rollback_plan: str = "",
        github_dry_run_result: dict[str, Any] | None = None,
        status: str = "draft",
    ) -> PRDraftArtifact:
        with start_span(
            "code_workspace.create_pr_draft",
            **{
                "db.table": "pr_draft_artifacts",
                "task_id": task_id,
                "workflow_id": workflow_id or "",
                "workspace_id": workspace_id,
                "status": status,
            },
        ):
            conn = await self._connect()
            try:
                row = await conn.fetchrow(
                    "INSERT INTO pr_draft_artifacts "
                    "(task_id, workflow_id, workspace_id, title, body, changed_files, "
                    " test_results, risk_assessment, rollback_plan, "
                    " github_dry_run_result, status) "
                    "VALUES ($1, $2, $3::uuid, $4, $5, $6::jsonb, $7::jsonb, "
                    " $8::jsonb, $9, $10::jsonb, $11) "
                    "ON CONFLICT (task_id) DO UPDATE SET "
                    " workflow_id = EXCLUDED.workflow_id, "
                    " workspace_id = EXCLUDED.workspace_id, "
                    " title = EXCLUDED.title, "
                    " body = EXCLUDED.body, "
                    " changed_files = EXCLUDED.changed_files, "
                    " test_results = EXCLUDED.test_results, "
                    " risk_assessment = EXCLUDED.risk_assessment, "
                    " rollback_plan = EXCLUDED.rollback_plan, "
                    " github_dry_run_result = EXCLUDED.github_dry_run_result, "
                    " status = EXCLUDED.status "
                    f"RETURNING {_PR_DRAFT_COLUMNS}",
                    task_id,
                    workflow_id,
                    workspace_id,
                    title,
                    body,
                    json.dumps(changed_files or []),
                    json.dumps(test_results or {}),
                    json.dumps(risk_assessment or {}),
                    rollback_plan,
                    json.dumps(github_dry_run_result or {}),
                    status,
                )
            finally:
                await conn.close()
            return _row_to_pr_draft(row)

    async def get_pr_draft_artifact(self, task_id: str) -> PRDraftArtifact | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                f"SELECT {_PR_DRAFT_COLUMNS} FROM pr_draft_artifacts WHERE task_id = $1",
                task_id,
            )
        finally:
            await conn.close()
        return _row_to_pr_draft(row) if row else None

    async def counts(self) -> dict[str, int]:
        """Aggregate counters for /operations/summary."""
        conn = await self._connect()
        try:
            totals = await conn.fetchrow(
                "SELECT "
                " (SELECT count(*) FROM code_workspaces) AS total_workspaces, "
                " (SELECT count(*) FROM code_workspaces WHERE status = 'ready_for_pr_draft') "
                "    AS ready_for_pr_draft, "
                " (SELECT count(*) FROM code_workspaces WHERE status = 'blocked') "
                "    AS blocked_count, "
                " (SELECT count(*) FROM code_workspaces WHERE generator_mode = "
                "    'deterministic_template') AS deterministic_count, "
                " (SELECT count(*) FROM code_change_artifacts) AS total_artifacts, "
                " (SELECT count(*) FROM code_change_artifacts WHERE validation_status = 'passed') "
                "    AS validated_artifacts, "
                " (SELECT count(*) FROM pr_draft_artifacts) AS total_pr_drafts"
            )
        finally:
            await conn.close()
        return {key: int(totals[key] or 0) for key in totals.keys()}
