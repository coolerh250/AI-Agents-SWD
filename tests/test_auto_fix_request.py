"""Stage 29 — auto_fix_requests row lifecycle assertions via QAStore."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import asyncpg

from shared.sdk.qa import QAStore


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _Row(dict):
    def __getitem__(self, key: str) -> Any:
        return dict.__getitem__(self, key)


class _Conn:
    def __init__(self, row=None, rows=None):
        self.row = row
        self.rows = rows or []
        self.calls: list[tuple[str, tuple]] = []

    async def fetchrow(self, sql, *params):
        self.calls.append((sql, params))
        return self.row

    async def fetch(self, sql, *params):
        self.calls.append((sql, params))
        return self.rows

    async def close(self):
        return None


def _patch(monkeypatch, conn):
    async def _connect(*a, **kw):
        return conn

    monkeypatch.setattr(asyncpg, "connect", _connect)


def _row(status="requested", attempt=1):
    return _Row(
        {
            "fix_request_id": uuid4(),
            "task_id": "t1",
            "workflow_id": "wf-1",
            "workspace_id": uuid4(),
            "qa_run_id": uuid4(),
            "finding_ids": json.dumps(["f-1"]),
            "attempt_number": attempt,
            "status": status,
            "requested_by": "qa-agent",
            "reason": "auto_fixable_blocking_findings",
            "fix_strategy": "deterministic",
            "result": json.dumps({}),
            "created_at": datetime.now(timezone.utc),
            "completed_at": None,
        }
    )


def test_auto_fix_request_lifecycle_transitions(monkeypatch):
    # Create a request -> mark running -> mark completed
    conn = _Conn(row=_row(status="requested"))
    _patch(monkeypatch, conn)
    store = QAStore("postgresql://stub")
    req = _run(
        store.create_auto_fix_request(
            task_id="t1",
            workflow_id="wf-1",
            workspace_id="00000000-0000-0000-0000-000000000001",
            qa_run_id="00000000-0000-0000-0000-000000000002",
            finding_ids=["f-1"],
            attempt_number=1,
        )
    )
    assert req.status == "requested"
    conn.row = _row(status="running")
    req = _run(store.update_auto_fix_request(req.fix_request_id, status="running"))
    assert req is not None
    assert req.status == "running"
    conn.row = _row(status="completed")
    req = _run(
        store.update_auto_fix_request(
            req.fix_request_id,
            status="completed",
            result={"applied": [{"finding_id": "f-1"}]},
        )
    )
    assert req is not None
    assert req.status == "completed"


def test_get_auto_fix_request_returns_none_on_invalid_uuid(monkeypatch):
    conn = _Conn(row=None)
    _patch(monkeypatch, conn)
    store = QAStore("postgresql://stub")
    assert _run(store.get_auto_fix_request("not-a-uuid")) is None


def test_list_auto_fix_requests_orders_chronologically(monkeypatch):
    conn = _Conn(rows=[_row(attempt=1), _row(attempt=2)])
    _patch(monkeypatch, conn)
    store = QAStore("postgresql://stub")
    rows = _run(store.list_auto_fix_requests("t1"))
    assert len(rows) == 2
    assert "ORDER BY created_at ASC" in conn.calls[-1][0]


def test_create_auto_fix_request_serializes_finding_ids_as_jsonb(monkeypatch):
    conn = _Conn(row=_row())
    _patch(monkeypatch, conn)
    store = QAStore("postgresql://stub")
    _run(
        store.create_auto_fix_request(
            task_id="t1",
            workflow_id="wf-1",
            workspace_id="00000000-0000-0000-0000-000000000003",
            qa_run_id="00000000-0000-0000-0000-000000000004",
            finding_ids=["f-a", "f-b"],
            attempt_number=1,
        )
    )
    sql, params = conn.calls[-1]
    assert "finding_ids" in sql
    # finding_ids serialized as JSON string in the params
    json_param = next((p for p in params if isinstance(p, str) and p.startswith("[")), None)
    assert json_param is not None
    assert json.loads(json_param) == ["f-a", "f-b"]
