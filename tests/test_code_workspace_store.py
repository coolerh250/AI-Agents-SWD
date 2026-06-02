"""Stage 28 — CodeWorkspaceStore unit tests with asyncpg stubbed."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import asyncpg

from shared.sdk.code_workspace import CodeWorkspaceStore


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _FakeRow(dict):
    def __getitem__(self, key: str) -> Any:
        return dict.__getitem__(self, key)


class _FakeConn:
    last_sql: str = ""
    last_params: tuple = ()

    def __init__(self, row: _FakeRow | None = None, rows: list[_FakeRow] | None = None):
        self._row = row
        self._rows = rows or []

    async def fetchrow(self, sql: str, *params: Any):
        _FakeConn.last_sql = sql
        _FakeConn.last_params = params
        return self._row

    async def fetch(self, sql: str, *params: Any):
        _FakeConn.last_sql = sql
        _FakeConn.last_params = params
        return self._rows

    async def close(self):
        return None


def _patch(monkeypatch, conn: _FakeConn):
    async def _connect(*args, **kwargs):
        return conn

    monkeypatch.setattr(asyncpg, "connect", _connect)


def _ws_row(task_id: str = "t1", status: str = "created") -> _FakeRow:
    now = datetime.now(timezone.utc)
    return _FakeRow(
        {
            "workspace_id": uuid4(),
            "task_id": task_id,
            "workflow_id": "wf-1",
            "work_item_id": uuid4(),
            "execution_mode": "delivery_task",
            "status": status,
            "base_commit": "abc123",
            "branch_name": "ai-agents/t1",
            "workspace_path": "/tmp/aiagents-workspaces/t1",
            "allowed_paths": json.dumps(["docs/generated/"]),
            "denied_paths": json.dumps([".github/*"]),
            "generator_mode": "deterministic_template",
            "blocked_reason": "",
            "created_by_agent": "development-agent",
            "created_at": now,
            "updated_at": now,
        }
    )


def _artifact_row(task_id: str = "t1", file_path: str = "docs/generated/t1.md") -> _FakeRow:
    now = datetime.now(timezone.utc)
    return _FakeRow(
        {
            "artifact_id": uuid4(),
            "task_id": task_id,
            "workflow_id": "wf-1",
            "workspace_id": uuid4(),
            "file_path": file_path,
            "change_type": "create",
            "before_sha": "0" * 64,
            "after_sha": "1" * 64,
            "diff_summary": "+5/-0 across 1 hunk(s)",
            "diff_text": "@@ -0,0 +1,5 @@\n+# hello",
            "generated_content_preview": "# hello",
            "validation_status": "pending",
            "created_at": now,
        }
    )


def _pr_draft_row(task_id: str = "t1") -> _FakeRow:
    now = datetime.now(timezone.utc)
    return _FakeRow(
        {
            "pr_draft_id": uuid4(),
            "task_id": task_id,
            "workflow_id": "wf-1",
            "workspace_id": uuid4(),
            "title": "[ai-agents-swd] documentation — t1",
            "body": "## Summary\n...",
            "changed_files": json.dumps([{"file_path": "docs/generated/t1.md"}]),
            "test_results": json.dumps({"status": "passed"}),
            "risk_assessment": json.dumps({"risk_level": "low"}),
            "rollback_plan": "Revert manually.",
            "github_dry_run_result": json.dumps({"dry_run": True}),
            "status": "ready",
            "created_at": now,
        }
    )


def test_create_workspace_upserts_by_task_id(monkeypatch):
    row = _ws_row()
    _patch(monkeypatch, _FakeConn(row=row))
    store = CodeWorkspaceStore("postgresql://stub")
    ws = _run(
        store.create_workspace(
            task_id="t1",
            workflow_id="wf-1",
            execution_mode="delivery_task",
            workspace_path="/tmp/aiagents-workspaces/t1",
            allowed_paths=["docs/generated/"],
            denied_paths=[".github/*"],
        )
    )
    assert ws.task_id == "t1"
    assert ws.execution_mode == "delivery_task"
    assert "ON CONFLICT (task_id)" in _FakeConn.last_sql


def test_get_workspace_returns_none_when_missing(monkeypatch):
    _patch(monkeypatch, _FakeConn(row=None))
    store = CodeWorkspaceStore("postgresql://stub")
    assert _run(store.get_workspace("missing")) is None


def test_list_workspaces_filters_and_orders(monkeypatch):
    _patch(monkeypatch, _FakeConn(rows=[_ws_row("a"), _ws_row("b", status="blocked")]))
    store = CodeWorkspaceStore("postgresql://stub")
    rows = _run(store.list_workspaces(status="blocked", limit=10))
    assert len(rows) == 2
    assert "ORDER BY created_at DESC LIMIT" in _FakeConn.last_sql


def test_update_workspace_status_writes_blocked_reason(monkeypatch):
    _patch(monkeypatch, _FakeConn(row=_ws_row(status="blocked")))
    store = CodeWorkspaceStore("postgresql://stub")
    ws = _run(store.update_workspace_status("t1", "blocked", blocked_reason="denied:infra"))
    assert ws is not None
    assert ws.status == "blocked"
    assert "blocked_reason = COALESCE" in _FakeConn.last_sql


def test_add_code_change_artifact_records_diff(monkeypatch):
    _patch(monkeypatch, _FakeConn(row=_artifact_row()))
    store = CodeWorkspaceStore("postgresql://stub")
    art = _run(
        store.add_code_change_artifact(
            task_id="t1",
            workflow_id="wf-1",
            workspace_id="00000000-0000-0000-0000-000000000001",
            file_path="docs/generated/t1.md",
            diff_summary="+5/-0",
            diff_text="@@ -0,0 +1,5 @@",
        )
    )
    assert art.file_path == "docs/generated/t1.md"
    assert art.change_type == "create"


def test_list_code_change_artifacts(monkeypatch):
    _patch(monkeypatch, _FakeConn(rows=[_artifact_row()]))
    store = CodeWorkspaceStore("postgresql://stub")
    rows = _run(store.list_code_change_artifacts("t1"))
    assert len(rows) == 1
    assert "ORDER BY created_at ASC" in _FakeConn.last_sql


def test_create_pr_draft_artifact_upserts(monkeypatch):
    _patch(monkeypatch, _FakeConn(row=_pr_draft_row()))
    store = CodeWorkspaceStore("postgresql://stub")
    draft = _run(
        store.create_pr_draft_artifact(
            task_id="t1",
            workflow_id="wf-1",
            workspace_id="00000000-0000-0000-0000-000000000001",
            title="[ai-agents-swd] documentation — t1",
            body="## Summary\n...",
            changed_files=[{"file_path": "docs/generated/t1.md"}],
        )
    )
    assert draft.status == "ready"
    assert "ON CONFLICT (task_id)" in _FakeConn.last_sql


def test_get_pr_draft_artifact_returns_none_when_missing(monkeypatch):
    _patch(monkeypatch, _FakeConn(row=None))
    store = CodeWorkspaceStore("postgresql://stub")
    assert _run(store.get_pr_draft_artifact("missing")) is None


def test_counts_returns_zero_dict_shape(monkeypatch):
    _patch(
        monkeypatch,
        _FakeConn(
            row=_FakeRow(
                {
                    "total_workspaces": 3,
                    "ready_for_pr_draft": 1,
                    "blocked_count": 1,
                    "deterministic_count": 3,
                    "total_artifacts": 5,
                    "validated_artifacts": 4,
                    "total_pr_drafts": 1,
                }
            )
        ),
    )
    store = CodeWorkspaceStore("postgresql://stub")
    counts = _run(store.counts())
    assert counts["total_workspaces"] == 3
    assert counts["blocked_count"] == 1
    assert counts["total_pr_drafts"] == 1
