"""asyncpg store for the Stage 29 QA tables."""

from __future__ import annotations

import json
import os
from typing import Any

import asyncpg

from shared.sdk.observability.tracing import start_span
from shared.sdk.qa.models import AutoFixRequest, QAFinding, QAValidationRun

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"

_RUN_COLUMNS = (
    "qa_run_id, task_id, workflow_id, workspace_id, pr_draft_id, status, "
    "validation_scope, qa_agent, total_findings, blocking_findings, "
    "non_blocking_findings, auto_fix_attempts, max_auto_fix_attempts, "
    "final_result, metadata, created_at, completed_at"
)

_FINDING_COLUMNS = (
    "finding_id, qa_run_id, task_id, workflow_id, workspace_id, severity, "
    "category, file_path, title, description, recommendation, auto_fixable, "
    "status, metadata, created_at, resolved_at"
)

_FIX_REQUEST_COLUMNS = (
    "fix_request_id, task_id, workflow_id, workspace_id, qa_run_id, finding_ids, "
    "attempt_number, status, requested_by, reason, fix_strategy, result, "
    "created_at, completed_at"
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


def _row_to_run(row: asyncpg.Record) -> QAValidationRun:
    return QAValidationRun(
        qa_run_id=str(row["qa_run_id"]),
        task_id=row["task_id"],
        workflow_id=row["workflow_id"],
        workspace_id=str(row["workspace_id"]) if row["workspace_id"] is not None else None,
        pr_draft_id=str(row["pr_draft_id"]) if row["pr_draft_id"] is not None else None,
        status=row["status"] or "started",
        validation_scope=row["validation_scope"] or "workspace",
        qa_agent=row["qa_agent"] or "qa-agent",
        total_findings=int(row["total_findings"] or 0),
        blocking_findings=int(row["blocking_findings"] or 0),
        non_blocking_findings=int(row["non_blocking_findings"] or 0),
        auto_fix_attempts=int(row["auto_fix_attempts"] or 0),
        max_auto_fix_attempts=int(row["max_auto_fix_attempts"] or 2),
        final_result=row["final_result"] or "not_applicable",
        metadata=_decode_json(row["metadata"], {}) or {},
        created_at=_iso(row["created_at"]),
        completed_at=_iso(row["completed_at"]),
    )


def _row_to_finding(row: asyncpg.Record) -> QAFinding:
    return QAFinding(
        finding_id=str(row["finding_id"]),
        qa_run_id=str(row["qa_run_id"]),
        task_id=row["task_id"],
        workflow_id=row["workflow_id"],
        workspace_id=str(row["workspace_id"]) if row["workspace_id"] is not None else None,
        severity=row["severity"] or "warning",
        category=row["category"] or "unknown",
        file_path=row["file_path"],
        title=row["title"] or "",
        description=row["description"] or "",
        recommendation=row["recommendation"] or "",
        auto_fixable=bool(row["auto_fixable"]),
        status=row["status"] or "open",
        metadata=_decode_json(row["metadata"], {}) or {},
        created_at=_iso(row["created_at"]),
        resolved_at=_iso(row["resolved_at"]),
    )


def _row_to_fix_request(row: asyncpg.Record) -> AutoFixRequest:
    return AutoFixRequest(
        fix_request_id=str(row["fix_request_id"]),
        task_id=row["task_id"],
        workflow_id=row["workflow_id"],
        workspace_id=str(row["workspace_id"]) if row["workspace_id"] is not None else None,
        qa_run_id=str(row["qa_run_id"]) if row["qa_run_id"] is not None else None,
        finding_ids=_decode_json(row["finding_ids"], []) or [],
        attempt_number=int(row["attempt_number"] or 1),
        status=row["status"] or "requested",
        requested_by=row["requested_by"] or "qa-agent",
        reason=row["reason"] or "",
        fix_strategy=row["fix_strategy"] or "deterministic",
        result=_decode_json(row["result"], {}) or {},
        created_at=_iso(row["created_at"]),
        completed_at=_iso(row["completed_at"]),
    )


class QAStore:
    """Wraps the three Stage 29 tables. Connection-per-call."""

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.database_url, timeout=5)

    # ------------------------------------------------------------------
    # qa_validation_runs
    # ------------------------------------------------------------------

    async def create_validation_run(
        self,
        *,
        task_id: str,
        workflow_id: str | None = None,
        workspace_id: str | None = None,
        pr_draft_id: str | None = None,
        status: str = "started",
        validation_scope: str = "workspace",
        qa_agent: str = "qa-agent",
        max_auto_fix_attempts: int = 2,
        auto_fix_attempts: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> QAValidationRun:
        with start_span(
            "qa.validation_start",
            **{
                "db.table": "qa_validation_runs",
                "task_id": task_id,
                "workflow_id": workflow_id or "",
                "workspace_id": workspace_id or "",
            },
        ):
            conn = await self._connect()
            try:
                row = await conn.fetchrow(
                    "INSERT INTO qa_validation_runs "
                    "(task_id, workflow_id, workspace_id, pr_draft_id, status, "
                    " validation_scope, qa_agent, max_auto_fix_attempts, "
                    " auto_fix_attempts, metadata) "
                    "VALUES ($1, $2, $3::uuid, $4::uuid, $5, $6, $7, $8, $9, $10::jsonb) "
                    f"RETURNING {_RUN_COLUMNS}",
                    task_id,
                    workflow_id,
                    workspace_id,
                    pr_draft_id,
                    status,
                    validation_scope,
                    qa_agent,
                    max_auto_fix_attempts,
                    auto_fix_attempts,
                    json.dumps(metadata or {}),
                )
            finally:
                await conn.close()
            return _row_to_run(row)

    async def complete_validation_run(
        self,
        qa_run_id: str,
        *,
        status: str,
        final_result: str,
        total_findings: int,
        blocking_findings: int,
        non_blocking_findings: int,
        auto_fix_attempts: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> QAValidationRun | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "UPDATE qa_validation_runs SET "
                " status = $2, final_result = $3, total_findings = $4, "
                " blocking_findings = $5, non_blocking_findings = $6, "
                " auto_fix_attempts = COALESCE($7, auto_fix_attempts), "
                " metadata = COALESCE($8::jsonb, metadata), "
                " completed_at = now() "
                f"WHERE qa_run_id = $1::uuid RETURNING {_RUN_COLUMNS}",
                qa_run_id,
                status,
                final_result,
                total_findings,
                blocking_findings,
                non_blocking_findings,
                auto_fix_attempts,
                json.dumps(metadata) if metadata is not None else None,
            )
        except (asyncpg.PostgresError, ValueError):
            row = None
        finally:
            await conn.close()
        return _row_to_run(row) if row else None

    async def get_latest_validation_run(self, task_id: str) -> QAValidationRun | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                f"SELECT {_RUN_COLUMNS} FROM qa_validation_runs "
                "WHERE task_id = $1 ORDER BY created_at DESC LIMIT 1",
                task_id,
            )
        finally:
            await conn.close()
        return _row_to_run(row) if row else None

    async def list_validation_runs(
        self,
        *,
        task_id: str | None = None,
        status: str | None = None,
        final_result: str | None = None,
        limit: int = 100,
    ) -> list[QAValidationRun]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                f"SELECT {_RUN_COLUMNS} FROM qa_validation_runs "
                "WHERE ($1::text IS NULL OR task_id = $1) "
                "AND ($2::text IS NULL OR status = $2) "
                "AND ($3::text IS NULL OR final_result = $3) "
                "ORDER BY created_at DESC LIMIT $4",
                task_id,
                status,
                final_result,
                limit,
            )
        finally:
            await conn.close()
        return [_row_to_run(r) for r in rows]

    # ------------------------------------------------------------------
    # qa_findings
    # ------------------------------------------------------------------

    async def add_finding(
        self,
        *,
        qa_run_id: str,
        task_id: str,
        workflow_id: str | None,
        workspace_id: str | None,
        severity: str,
        category: str,
        title: str,
        description: str,
        recommendation: str = "",
        file_path: str | None = None,
        auto_fixable: bool = False,
        status: str = "open",
        metadata: dict[str, Any] | None = None,
    ) -> QAFinding:
        with start_span(
            "qa.create_finding",
            **{
                "db.table": "qa_findings",
                "task_id": task_id,
                "qa_run_id": qa_run_id,
                "severity": severity,
                "category": category,
                "auto_fixable": str(auto_fixable).lower(),
            },
        ):
            conn = await self._connect()
            try:
                row = await conn.fetchrow(
                    "INSERT INTO qa_findings "
                    "(qa_run_id, task_id, workflow_id, workspace_id, severity, "
                    " category, file_path, title, description, recommendation, "
                    " auto_fixable, status, metadata) "
                    "VALUES ($1::uuid, $2, $3, $4::uuid, $5, $6, $7, $8, $9, "
                    " $10, $11, $12, $13::jsonb) "
                    f"RETURNING {_FINDING_COLUMNS}",
                    qa_run_id,
                    task_id,
                    workflow_id,
                    workspace_id,
                    severity,
                    category,
                    file_path,
                    title,
                    description,
                    recommendation,
                    auto_fixable,
                    status,
                    json.dumps(metadata or {}),
                )
            finally:
                await conn.close()
            return _row_to_finding(row)

    async def list_findings(
        self,
        task_id: str,
        *,
        qa_run_id: str | None = None,
        status: str | None = None,
        severity: str | None = None,
        limit: int = 200,
    ) -> list[QAFinding]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                f"SELECT {_FINDING_COLUMNS} FROM qa_findings "
                "WHERE task_id = $1 "
                "AND ($2::uuid IS NULL OR qa_run_id = $2::uuid) "
                "AND ($3::text IS NULL OR status = $3) "
                "AND ($4::text IS NULL OR severity = $4) "
                "ORDER BY created_at ASC LIMIT $5",
                task_id,
                qa_run_id,
                status,
                severity,
                limit,
            )
        except (asyncpg.PostgresError, ValueError):
            rows = []
        finally:
            await conn.close()
        return [_row_to_finding(r) for r in rows]

    async def update_finding_status(
        self,
        finding_id: str,
        *,
        status: str,
        resolved: bool = False,
    ) -> QAFinding | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "UPDATE qa_findings SET status = $2, "
                " resolved_at = CASE WHEN $3 THEN now() ELSE resolved_at END "
                f"WHERE finding_id = $1::uuid RETURNING {_FINDING_COLUMNS}",
                finding_id,
                status,
                resolved,
            )
        except (asyncpg.PostgresError, ValueError):
            row = None
        finally:
            await conn.close()
        return _row_to_finding(row) if row else None

    # ------------------------------------------------------------------
    # auto_fix_requests
    # ------------------------------------------------------------------

    async def create_auto_fix_request(
        self,
        *,
        task_id: str,
        workflow_id: str | None,
        workspace_id: str | None,
        qa_run_id: str | None,
        finding_ids: list[str],
        attempt_number: int,
        status: str = "requested",
        requested_by: str = "qa-agent",
        reason: str = "",
        fix_strategy: str = "deterministic",
        result: dict[str, Any] | None = None,
    ) -> AutoFixRequest:
        with start_span(
            "qa.request_auto_fix",
            **{
                "db.table": "auto_fix_requests",
                "task_id": task_id,
                "qa_run_id": qa_run_id or "",
                "attempt_number": str(attempt_number),
                "finding_count": str(len(finding_ids)),
            },
        ):
            conn = await self._connect()
            try:
                row = await conn.fetchrow(
                    "INSERT INTO auto_fix_requests "
                    "(task_id, workflow_id, workspace_id, qa_run_id, finding_ids, "
                    " attempt_number, status, requested_by, reason, fix_strategy, "
                    " result) "
                    "VALUES ($1, $2, $3::uuid, $4::uuid, $5::jsonb, $6, $7, $8, $9, "
                    " $10, $11::jsonb) "
                    f"RETURNING {_FIX_REQUEST_COLUMNS}",
                    task_id,
                    workflow_id,
                    workspace_id,
                    qa_run_id,
                    json.dumps(finding_ids or []),
                    attempt_number,
                    status,
                    requested_by,
                    reason,
                    fix_strategy,
                    json.dumps(result or {}),
                )
            finally:
                await conn.close()
            return _row_to_fix_request(row)

    async def update_auto_fix_request(
        self,
        fix_request_id: str,
        *,
        status: str,
        result: dict[str, Any] | None = None,
    ) -> AutoFixRequest | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "UPDATE auto_fix_requests SET "
                " status = $2, "
                " result = COALESCE($3::jsonb, result), "
                " completed_at = CASE WHEN $2 IN ('completed','failed','blocked',"
                "                                  'max_attempts_exceeded') "
                "                     THEN now() ELSE completed_at END "
                f"WHERE fix_request_id = $1::uuid RETURNING {_FIX_REQUEST_COLUMNS}",
                fix_request_id,
                status,
                json.dumps(result) if result is not None else None,
            )
        except (asyncpg.PostgresError, ValueError):
            row = None
        finally:
            await conn.close()
        return _row_to_fix_request(row) if row else None

    async def get_auto_fix_request(self, fix_request_id: str) -> AutoFixRequest | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                f"SELECT {_FIX_REQUEST_COLUMNS} FROM auto_fix_requests "
                "WHERE fix_request_id = $1::uuid",
                fix_request_id,
            )
        except (asyncpg.PostgresError, ValueError):
            row = None
        finally:
            await conn.close()
        return _row_to_fix_request(row) if row else None

    async def list_auto_fix_requests(
        self,
        task_id: str,
        *,
        status: str | None = None,
        limit: int = 100,
    ) -> list[AutoFixRequest]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                f"SELECT {_FIX_REQUEST_COLUMNS} FROM auto_fix_requests "
                "WHERE task_id = $1 "
                "AND ($2::text IS NULL OR status = $2) "
                "ORDER BY created_at ASC LIMIT $3",
                task_id,
                status,
                limit,
            )
        finally:
            await conn.close()
        return [_row_to_fix_request(r) for r in rows]

    async def counts(self) -> dict[str, int]:
        """Aggregate counters for /operations/summary."""
        conn = await self._connect()
        try:
            totals = await conn.fetchrow(
                "SELECT "
                " (SELECT count(*) FROM qa_validation_runs) AS total_validation_runs, "
                " (SELECT count(*) FROM qa_validation_runs WHERE final_result = 'pass') "
                "    AS passed_runs, "
                " (SELECT count(*) FROM qa_validation_runs WHERE final_result = 'fail') "
                "    AS failed_runs, "
                " (SELECT count(*) FROM qa_validation_runs WHERE status = "
                "    'blocked_for_human_review') AS blocked_for_human_review_count, "
                " (SELECT count(*) FROM auto_fix_requests WHERE status = 'requested' "
                "    OR status = 'running') AS auto_fix_requested_count, "
                " (SELECT count(*) FROM qa_findings) AS total_findings"
            )
        finally:
            await conn.close()
        return {key: int(totals[key] or 0) for key in totals.keys()}
