"""Stage 27 — TaskExecutionStore unit tests with asyncpg stubbed."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import asyncpg

from shared.sdk.task_execution import TaskExecutionStore


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


def _patch_connect(monkeypatch, conn: _FakeConn):
    async def _connect(*args, **kwargs):
        return conn

    monkeypatch.setattr(asyncpg, "connect", _connect)


def _work_item_row(task_id: str = "t1", status: str = "intake_received") -> _FakeRow:
    now = datetime.now(timezone.utc)
    return _FakeRow(
        {
            "work_item_id": uuid4(),
            "task_id": task_id,
            "workflow_id": "wf-1",
            "title": "title",
            "description": "desc",
            "request_type": "dev.test",
            "execution_mode": "delivery_task",
            "status": status,
            "priority": "normal",
            "source": "discord",
            "requester_id": "u1",
            "channel_id": "c1",
            "task_category": "general",
            "development_required": True,
            "github_required": False,
            "clarification_required": False,
            "acceptance_criteria": None,
            "definition_of_done": None,
            "execution_plan": json.dumps({"stages": ["intake"]}),
            "assumptions": json.dumps(["a1"]),
            "open_questions": json.dumps([]),
            "risks": json.dumps([]),
            "scrum_enabled": False,
            "scrum_metadata": None,
            "created_at": now,
            "updated_at": now,
        }
    )


def _discussion_row(task_id: str = "t1") -> _FakeRow:
    return _FakeRow(
        {
            "discussion_id": uuid4(),
            "task_id": task_id,
            "workflow_id": "wf-1",
            "agent": "requirement-agent",
            "role": "analyst",
            "message_type": "analysis",
            "content": "looks ok",
            "confidence": 0.8,
            "references": json.dumps({"k": "v"}),
            "created_at": datetime.now(timezone.utc),
        }
    )


def _clarification_row(task_id: str = "t1", status: str = "open") -> _FakeRow:
    return _FakeRow(
        {
            "clarification_id": uuid4(),
            "task_id": task_id,
            "workflow_id": "wf-1",
            "question": "what is the goal?",
            "requested_by_agent": "requirement-agent",
            "status": status,
            "user_response": "answer" if status == "answered" else None,
            "channel_id": "c1",
            "message_id": "m1",
            "created_at": datetime.now(timezone.utc),
            "answered_at": datetime.now(timezone.utc) if status == "answered" else None,
        }
    )


def test_create_work_item_upserts(monkeypatch):
    row = _work_item_row()
    _patch_connect(monkeypatch, _FakeConn(row=row))
    store = TaskExecutionStore(database_url="postgresql://example")
    out = _run(
        store.create_work_item(
            task_id="t1",
            workflow_id="wf-1",
            title="title",
            description="desc",
            request_type="dev.test",
            execution_mode="delivery_task",
            status="intake_received",
            development_required=True,
        )
    )
    assert out.task_id == "t1"
    assert out.execution_mode == "delivery_task"
    assert "INSERT INTO task_work_items" in _FakeConn.last_sql
    assert "ON CONFLICT (task_id) DO UPDATE" in _FakeConn.last_sql


def test_get_work_item_returns_none_when_missing(monkeypatch):
    _patch_connect(monkeypatch, _FakeConn(row=None))
    store = TaskExecutionStore(database_url="postgresql://example")
    out = _run(store.get_work_item("missing"))
    assert out is None


def test_list_work_items_filters_by_status(monkeypatch):
    rows = [_work_item_row(task_id=f"t{i}") for i in range(3)]
    _patch_connect(monkeypatch, _FakeConn(rows=rows))
    store = TaskExecutionStore(database_url="postgresql://example")
    items = _run(store.list_work_items(status="ready_for_development"))
    assert len(items) == 3
    # status / execution_mode / limit positional check
    assert _FakeConn.last_params[0] == "ready_for_development"


def test_update_work_item_status(monkeypatch):
    row = _work_item_row(status="ready_for_development")
    _patch_connect(monkeypatch, _FakeConn(row=row))
    store = TaskExecutionStore(database_url="postgresql://example")
    out = _run(store.update_work_item_status("t1", "ready_for_development"))
    assert out is not None
    assert out.status == "ready_for_development"


def test_set_acceptance_criteria_serialises_json(monkeypatch):
    row = _work_item_row()
    _patch_connect(monkeypatch, _FakeConn(row=row))
    store = TaskExecutionStore(database_url="postgresql://example")
    _run(store.set_acceptance_criteria("t1", ["one", "two"]))
    assert _FakeConn.last_params[1] == json.dumps(["one", "two"])


def test_add_agent_discussion_inserts(monkeypatch):
    row = _discussion_row()
    _patch_connect(monkeypatch, _FakeConn(row=row))
    store = TaskExecutionStore(database_url="postgresql://example")
    out = _run(
        store.add_agent_discussion(
            task_id="t1",
            workflow_id="wf-1",
            agent="requirement-agent",
            message_type="analysis",
            content="looks ok",
        )
    )
    assert out.agent == "requirement-agent"
    assert out.message_type == "analysis"
    assert "INSERT INTO agent_discussions" in _FakeConn.last_sql


def test_list_agent_discussions(monkeypatch):
    rows = [_discussion_row(), _discussion_row()]
    _patch_connect(monkeypatch, _FakeConn(rows=rows))
    store = TaskExecutionStore(database_url="postgresql://example")
    out = _run(store.list_agent_discussions("t1"))
    assert len(out) == 2


def test_create_clarification_request(monkeypatch):
    row = _clarification_row()
    _patch_connect(monkeypatch, _FakeConn(row=row))
    store = TaskExecutionStore(database_url="postgresql://example")
    out = _run(
        store.create_clarification_request(
            task_id="t1",
            workflow_id="wf-1",
            question="what is the goal?",
        )
    )
    assert out.status == "open"
    assert "INSERT INTO clarification_requests" in _FakeConn.last_sql


def test_answer_clarification_request(monkeypatch):
    row = _clarification_row(status="answered")
    _patch_connect(monkeypatch, _FakeConn(row=row))
    store = TaskExecutionStore(database_url="postgresql://example")
    out = _run(
        store.answer_clarification_request(
            str(uuid4()),
            user_response="here is the answer",
        )
    )
    assert out is not None
    assert out.status == "answered"
    assert "status = 'answered'" in _FakeConn.last_sql
