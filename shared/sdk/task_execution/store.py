"""asyncpg store for the Stage 27 task_execution tables."""

from __future__ import annotations

import json
import os
from typing import Any

import asyncpg

from shared.sdk.observability.tracing import start_span
from shared.sdk.task_execution.models import (
    AgentDiscussion,
    ClarificationRequest,
    TaskWorkItem,
)

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"

_WORK_ITEM_COLUMNS = (
    "work_item_id, task_id, workflow_id, title, description, request_type, "
    "execution_mode, status, priority, source, requester_id, channel_id, "
    "task_category, development_required, github_required, clarification_required, "
    "acceptance_criteria, definition_of_done, execution_plan, assumptions, "
    "open_questions, risks, scrum_enabled, scrum_metadata, created_at, updated_at"
)

_DISCUSSION_COLUMNS = (
    "discussion_id, task_id, workflow_id, agent, role, message_type, content, "
    "confidence, refs, created_at"
)

_CLARIFICATION_COLUMNS = (
    "clarification_id, task_id, workflow_id, question, requested_by_agent, "
    "status, user_response, channel_id, message_id, created_at, answered_at"
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


def _row_to_work_item(row: asyncpg.Record) -> TaskWorkItem:
    return TaskWorkItem(
        work_item_id=str(row["work_item_id"]),
        task_id=row["task_id"],
        workflow_id=row["workflow_id"],
        title=row["title"] or "",
        description=row["description"] or "",
        request_type=row["request_type"] or "unknown",
        execution_mode=row["execution_mode"] or "simple_task",
        status=row["status"] or "intake_received",
        priority=row["priority"] or "normal",
        source=row["source"] or "discord",
        requester_id=row["requester_id"],
        channel_id=row["channel_id"],
        task_category=row["task_category"] or "general",
        development_required=bool(row["development_required"]),
        github_required=bool(row["github_required"]),
        clarification_required=bool(row["clarification_required"]),
        acceptance_criteria=_decode_json(row["acceptance_criteria"], None),
        definition_of_done=_decode_json(row["definition_of_done"], None),
        execution_plan=_decode_json(row["execution_plan"], {}) or {},
        assumptions=_decode_json(row["assumptions"], []) or [],
        open_questions=_decode_json(row["open_questions"], []) or [],
        risks=_decode_json(row["risks"], []) or [],
        scrum_enabled=bool(row["scrum_enabled"]),
        scrum_metadata=_decode_json(row["scrum_metadata"], None),
        created_at=_iso(row["created_at"]),
        updated_at=_iso(row["updated_at"]),
    )


def _row_to_discussion(row: asyncpg.Record) -> AgentDiscussion:
    return AgentDiscussion(
        discussion_id=str(row["discussion_id"]),
        task_id=row["task_id"],
        workflow_id=row["workflow_id"],
        agent=row["agent"],
        role=row["role"] or "analyst",
        message_type=row["message_type"] or "analysis",
        content=row["content"] or "",
        confidence=float(row["confidence"] or 0.5),
        references=_decode_json(row["refs"], {}) or {},
        created_at=_iso(row["created_at"]),
    )


def _row_to_clarification(row: asyncpg.Record) -> ClarificationRequest:
    return ClarificationRequest(
        clarification_id=str(row["clarification_id"]),
        task_id=row["task_id"],
        workflow_id=row["workflow_id"],
        question=row["question"] or "",
        requested_by_agent=row["requested_by_agent"] or "requirement-agent",
        status=row["status"] or "open",
        user_response=row["user_response"],
        channel_id=row["channel_id"],
        message_id=row["message_id"],
        created_at=_iso(row["created_at"]),
        answered_at=_iso(row["answered_at"]),
    )


class TaskExecutionStore:
    """Wraps the three Stage 27 tables.

    Every call opens a short-lived asyncpg connection. ``DATABASE_URL``
    drives the dsn; defaults to the local/test cluster's trust-auth
    postgres for the test fixtures. Stage 26 staging uses
    ``aiagents_app:${POSTGRES_PASSWORD}@postgres/aiagents`` injected
    via the staging compose env.
    """

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.database_url, timeout=5)

    # ------------------------------------------------------------------
    # work items
    # ------------------------------------------------------------------

    async def create_work_item(
        self,
        *,
        task_id: str,
        workflow_id: str | None = None,
        title: str = "",
        description: str = "",
        request_type: str = "unknown",
        execution_mode: str = "simple_task",
        status: str = "intake_received",
        priority: str = "normal",
        source: str = "discord",
        requester_id: str | None = None,
        channel_id: str | None = None,
        task_category: str = "general",
        development_required: bool = False,
        github_required: bool = False,
        clarification_required: bool = False,
        acceptance_criteria: list[Any] | None = None,
        definition_of_done: list[Any] | None = None,
        execution_plan: dict[str, Any] | None = None,
        assumptions: list[Any] | None = None,
        open_questions: list[Any] | None = None,
        risks: list[Any] | None = None,
        scrum_enabled: bool = False,
        scrum_metadata: dict[str, Any] | None = None,
    ) -> TaskWorkItem:
        """Upsert one work item by ``task_id``."""
        with start_span(
            "task_execution.create_work_item",
            **{
                "db.table": "task_work_items",
                "task_id": task_id,
                "workflow_id": workflow_id or "",
                "execution_mode": execution_mode,
                "status": status,
            },
        ):
            conn = await self._connect()
            try:
                row = await conn.fetchrow(
                    "INSERT INTO task_work_items "
                    "(task_id, workflow_id, title, description, request_type, "
                    " execution_mode, status, priority, source, requester_id, "
                    " channel_id, task_category, development_required, "
                    " github_required, clarification_required, "
                    " acceptance_criteria, definition_of_done, execution_plan, "
                    " assumptions, open_questions, risks, scrum_enabled, "
                    " scrum_metadata) "
                    "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, "
                    " $13, $14, $15, $16::jsonb, $17::jsonb, $18::jsonb, "
                    " $19::jsonb, $20::jsonb, $21::jsonb, $22, $23::jsonb) "
                    "ON CONFLICT (task_id) DO UPDATE SET "
                    " workflow_id = EXCLUDED.workflow_id, "
                    " title = EXCLUDED.title, "
                    " description = EXCLUDED.description, "
                    " request_type = EXCLUDED.request_type, "
                    " execution_mode = EXCLUDED.execution_mode, "
                    " status = EXCLUDED.status, "
                    " priority = EXCLUDED.priority, "
                    " source = EXCLUDED.source, "
                    " requester_id = EXCLUDED.requester_id, "
                    " channel_id = EXCLUDED.channel_id, "
                    " task_category = EXCLUDED.task_category, "
                    " development_required = EXCLUDED.development_required, "
                    " github_required = EXCLUDED.github_required, "
                    " clarification_required = EXCLUDED.clarification_required, "
                    " acceptance_criteria = EXCLUDED.acceptance_criteria, "
                    " definition_of_done = EXCLUDED.definition_of_done, "
                    " execution_plan = EXCLUDED.execution_plan, "
                    " assumptions = EXCLUDED.assumptions, "
                    " open_questions = EXCLUDED.open_questions, "
                    " risks = EXCLUDED.risks, "
                    " scrum_enabled = EXCLUDED.scrum_enabled, "
                    " scrum_metadata = EXCLUDED.scrum_metadata, "
                    " updated_at = now() "
                    f"RETURNING {_WORK_ITEM_COLUMNS}",
                    task_id,
                    workflow_id,
                    title,
                    description,
                    request_type,
                    execution_mode,
                    status,
                    priority,
                    source,
                    requester_id,
                    channel_id,
                    task_category,
                    development_required,
                    github_required,
                    clarification_required,
                    json.dumps(acceptance_criteria) if acceptance_criteria is not None else None,
                    json.dumps(definition_of_done) if definition_of_done is not None else None,
                    json.dumps(execution_plan or {}),
                    json.dumps(assumptions or []),
                    json.dumps(open_questions or []),
                    json.dumps(risks or []),
                    scrum_enabled,
                    json.dumps(scrum_metadata) if scrum_metadata is not None else None,
                )
            finally:
                await conn.close()
            return _row_to_work_item(row)

    async def get_work_item(self, task_id: str) -> TaskWorkItem | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                f"SELECT {_WORK_ITEM_COLUMNS} FROM task_work_items WHERE task_id = $1",
                task_id,
            )
        finally:
            await conn.close()
        return _row_to_work_item(row) if row else None

    async def list_work_items(
        self,
        *,
        status: str | None = None,
        execution_mode: str | None = None,
        limit: int = 100,
    ) -> list[TaskWorkItem]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                f"SELECT {_WORK_ITEM_COLUMNS} FROM task_work_items "
                "WHERE ($1::text IS NULL OR status = $1) "
                "AND ($2::text IS NULL OR execution_mode = $2) "
                "ORDER BY created_at DESC LIMIT $3",
                status,
                execution_mode,
                limit,
            )
        finally:
            await conn.close()
        return [_row_to_work_item(r) for r in rows]

    async def update_work_item_status(self, task_id: str, status: str) -> TaskWorkItem | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "UPDATE task_work_items SET status = $2, updated_at = now() "
                f"WHERE task_id = $1 RETURNING {_WORK_ITEM_COLUMNS}",
                task_id,
                status,
            )
        finally:
            await conn.close()
        return _row_to_work_item(row) if row else None

    async def update_execution_mode(
        self, task_id: str, execution_mode: str, *, scrum_enabled: bool | None = None
    ) -> TaskWorkItem | None:
        conn = await self._connect()
        try:
            if scrum_enabled is None:
                scrum_enabled = execution_mode == "scrum_project"
            row = await conn.fetchrow(
                "UPDATE task_work_items SET execution_mode = $2, scrum_enabled = $3, "
                "updated_at = now() "
                f"WHERE task_id = $1 RETURNING {_WORK_ITEM_COLUMNS}",
                task_id,
                execution_mode,
                bool(scrum_enabled),
            )
        finally:
            await conn.close()
        return _row_to_work_item(row) if row else None

    async def set_execution_plan(self, task_id: str, plan: dict[str, Any]) -> TaskWorkItem | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "UPDATE task_work_items SET execution_plan = $2::jsonb, "
                "updated_at = now() "
                f"WHERE task_id = $1 RETURNING {_WORK_ITEM_COLUMNS}",
                task_id,
                json.dumps(plan or {}),
            )
        finally:
            await conn.close()
        return _row_to_work_item(row) if row else None

    async def set_acceptance_criteria(
        self, task_id: str, criteria: list[Any]
    ) -> TaskWorkItem | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "UPDATE task_work_items SET acceptance_criteria = $2::jsonb, "
                "updated_at = now() "
                f"WHERE task_id = $1 RETURNING {_WORK_ITEM_COLUMNS}",
                task_id,
                json.dumps(criteria or []),
            )
        finally:
            await conn.close()
        return _row_to_work_item(row) if row else None

    async def set_definition_of_done(self, task_id: str, dod: list[Any]) -> TaskWorkItem | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "UPDATE task_work_items SET definition_of_done = $2::jsonb, "
                "updated_at = now() "
                f"WHERE task_id = $1 RETURNING {_WORK_ITEM_COLUMNS}",
                task_id,
                json.dumps(dod or []),
            )
        finally:
            await conn.close()
        return _row_to_work_item(row) if row else None

    # ------------------------------------------------------------------
    # agent discussions
    # ------------------------------------------------------------------

    async def add_agent_discussion(
        self,
        *,
        task_id: str,
        workflow_id: str | None,
        agent: str,
        message_type: str,
        content: str,
        role: str = "analyst",
        confidence: float = 0.5,
        references: dict[str, Any] | None = None,
    ) -> AgentDiscussion:
        with start_span(
            "task_execution.record_agent_discussion",
            **{
                "db.table": "agent_discussions",
                "task_id": task_id,
                "workflow_id": workflow_id or "",
                "agent": agent,
                "message_type": message_type,
            },
        ):
            conn = await self._connect()
            try:
                row = await conn.fetchrow(
                    "INSERT INTO agent_discussions "
                    "(task_id, workflow_id, agent, role, message_type, content, "
                    " confidence, refs) "
                    "VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb) "
                    f"RETURNING {_DISCUSSION_COLUMNS}",
                    task_id,
                    workflow_id,
                    agent,
                    role,
                    message_type,
                    content,
                    confidence,
                    json.dumps(references or {}),
                )
            finally:
                await conn.close()
            return _row_to_discussion(row)

    async def list_agent_discussions(
        self, task_id: str, *, limit: int = 200
    ) -> list[AgentDiscussion]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                f"SELECT {_DISCUSSION_COLUMNS} FROM agent_discussions "
                "WHERE task_id = $1 ORDER BY created_at ASC LIMIT $2",
                task_id,
                limit,
            )
        finally:
            await conn.close()
        return [_row_to_discussion(r) for r in rows]

    # ------------------------------------------------------------------
    # clarifications
    # ------------------------------------------------------------------

    async def create_clarification_request(
        self,
        *,
        task_id: str,
        workflow_id: str | None,
        question: str,
        requested_by_agent: str = "requirement-agent",
        channel_id: str | None = None,
        message_id: str | None = None,
    ) -> ClarificationRequest:
        with start_span(
            "task_execution.create_clarification",
            **{
                "db.table": "clarification_requests",
                "task_id": task_id,
                "workflow_id": workflow_id or "",
                "requested_by_agent": requested_by_agent,
            },
        ):
            conn = await self._connect()
            try:
                row = await conn.fetchrow(
                    "INSERT INTO clarification_requests "
                    "(task_id, workflow_id, question, requested_by_agent, "
                    " channel_id, message_id) "
                    "VALUES ($1, $2, $3, $4, $5, $6) "
                    f"RETURNING {_CLARIFICATION_COLUMNS}",
                    task_id,
                    workflow_id,
                    question,
                    requested_by_agent,
                    channel_id,
                    message_id,
                )
            finally:
                await conn.close()
            return _row_to_clarification(row)

    async def get_clarification_request(self, clarification_id: str) -> ClarificationRequest | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                f"SELECT {_CLARIFICATION_COLUMNS} FROM clarification_requests "
                "WHERE clarification_id = $1::uuid",
                clarification_id,
            )
        except (asyncpg.PostgresError, ValueError):
            row = None
        finally:
            await conn.close()
        return _row_to_clarification(row) if row else None

    async def list_clarification_requests(
        self, task_id: str, *, status: str | None = None
    ) -> list[ClarificationRequest]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                f"SELECT {_CLARIFICATION_COLUMNS} FROM clarification_requests "
                "WHERE task_id = $1 AND ($2::text IS NULL OR status = $2) "
                "ORDER BY created_at ASC",
                task_id,
                status,
            )
        finally:
            await conn.close()
        return [_row_to_clarification(r) for r in rows]

    async def answer_clarification_request(
        self,
        clarification_id: str,
        *,
        user_response: str,
        channel_id: str | None = None,
        message_id: str | None = None,
    ) -> ClarificationRequest | None:
        with start_span(
            "task_execution.answer_clarification",
            **{
                "db.table": "clarification_requests",
                "clarification_id": clarification_id,
            },
        ):
            conn = await self._connect()
            try:
                row = await conn.fetchrow(
                    "UPDATE clarification_requests SET "
                    " status = 'answered', "
                    " user_response = $2, "
                    " channel_id = COALESCE($3, channel_id), "
                    " message_id = COALESCE($4, message_id), "
                    " answered_at = now() "
                    "WHERE clarification_id = $1::uuid AND status = 'open' "
                    f"RETURNING {_CLARIFICATION_COLUMNS}",
                    clarification_id,
                    user_response,
                    channel_id,
                    message_id,
                )
            except (asyncpg.PostgresError, ValueError):
                row = None
            finally:
                await conn.close()
            return _row_to_clarification(row) if row else None

    async def counts(self) -> dict[str, int]:
        """Aggregate counts for /operations/summary."""
        conn = await self._connect()
        try:
            totals = await conn.fetchrow(
                "SELECT "
                " count(*) AS total_work_items, "
                " count(*) FILTER (WHERE execution_mode = 'simple_task') AS simple_task_count, "
                " count(*) FILTER (WHERE execution_mode = 'delivery_task') AS delivery_task_count, "
                " count(*) FILTER (WHERE execution_mode = 'scrum_project') AS scrum_project_count, "
                " count(*) FILTER (WHERE status = 'needs_clarification') AS needs_clarification_count, "
                " count(*) FILTER (WHERE status = 'ready_for_development') AS ready_for_development_count, "
                " count(*) FILTER (WHERE status = 'blocked') AS blocked_count "
                "FROM task_work_items"
            )
        finally:
            await conn.close()
        return {key: int(totals[key] or 0) for key in totals.keys()}
