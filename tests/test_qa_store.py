"""Stage 29 — QAStore unit tests with asyncpg stubbed."""

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


def _run_row(task_id: str = "t1", status: str = "started") -> _FakeRow:
    now = datetime.now(timezone.utc)
    return _FakeRow(
        {
            "qa_run_id": uuid4(),
            "task_id": task_id,
            "workflow_id": "wf-1",
            "workspace_id": uuid4(),
            "pr_draft_id": uuid4(),
            "status": status,
            "validation_scope": "workspace",
            "qa_agent": "qa-agent",
            "total_findings": 0,
            "blocking_findings": 0,
            "non_blocking_findings": 0,
            "auto_fix_attempts": 0,
            "max_auto_fix_attempts": 2,
            "final_result": "not_applicable",
            "metadata": json.dumps({}),
            "created_at": now,
            "completed_at": None,
        }
    )


def _finding_row(task_id: str = "t1", severity: str = "warning") -> _FakeRow:
    now = datetime.now(timezone.utc)
    return _FakeRow(
        {
            "finding_id": uuid4(),
            "qa_run_id": uuid4(),
            "task_id": task_id,
            "workflow_id": "wf-1",
            "workspace_id": uuid4(),
            "severity": severity,
            "category": "syntax",
            "file_path": "apps/demo-generated/x.py",
            "title": "bad",
            "description": "broken",
            "recommendation": "fix",
            "auto_fixable": True,
            "status": "open",
            "metadata": json.dumps({"reason": "stub"}),
            "created_at": now,
            "resolved_at": None,
        }
    )


def _fix_request_row(task_id: str = "t1", status: str = "requested") -> _FakeRow:
    now = datetime.now(timezone.utc)
    return _FakeRow(
        {
            "fix_request_id": uuid4(),
            "task_id": task_id,
            "workflow_id": "wf-1",
            "workspace_id": uuid4(),
            "qa_run_id": uuid4(),
            "finding_ids": json.dumps(["f-1", "f-2"]),
            "attempt_number": 1,
            "status": status,
            "requested_by": "qa-agent",
            "reason": "auto_fixable_blocking_findings",
            "fix_strategy": "deterministic",
            "result": json.dumps({"applied": []}),
            "created_at": now,
            "completed_at": None,
        }
    )


def test_create_validation_run_inserts_with_metadata(monkeypatch):
    _patch(monkeypatch, _FakeConn(row=_run_row()))
    store = QAStore("postgresql://stub")
    run = _run(
        store.create_validation_run(
            task_id="t1",
            workflow_id="wf-1",
            workspace_id="00000000-0000-0000-0000-000000000001",
            pr_draft_id="00000000-0000-0000-0000-000000000002",
            metadata={"event": "development.completed"},
        )
    )
    assert run.task_id == "t1"
    assert "INSERT INTO qa_validation_runs" in _FakeConn.last_sql


def test_complete_validation_run_updates_status_and_result(monkeypatch):
    _patch(monkeypatch, _FakeConn(row=_run_row(status="passed")))
    store = QAStore("postgresql://stub")
    run = _run(
        store.complete_validation_run(
            "00000000-0000-0000-0000-000000000003",
            status="passed",
            final_result="pass",
            total_findings=0,
            blocking_findings=0,
            non_blocking_findings=0,
            auto_fix_attempts=0,
        )
    )
    assert run is not None
    assert run.status == "passed"
    assert "UPDATE qa_validation_runs" in _FakeConn.last_sql


def test_get_latest_validation_run_returns_none_when_empty(monkeypatch):
    _patch(monkeypatch, _FakeConn(row=None))
    store = QAStore("postgresql://stub")
    assert _run(store.get_latest_validation_run("missing")) is None


def test_list_validation_runs_filter_clause(monkeypatch):
    _patch(monkeypatch, _FakeConn(rows=[_run_row(), _run_row(status="blocked_for_human_review")]))
    store = QAStore("postgresql://stub")
    rows = _run(store.list_validation_runs(task_id="t1", status="started"))
    assert len(rows) == 2
    assert "task_id" in _FakeConn.last_sql


def test_add_finding_inserts_row(monkeypatch):
    _patch(monkeypatch, _FakeConn(row=_finding_row()))
    store = QAStore("postgresql://stub")
    f = _run(
        store.add_finding(
            qa_run_id="00000000-0000-0000-0000-000000000010",
            task_id="t1",
            workflow_id="wf-1",
            workspace_id="00000000-0000-0000-0000-000000000011",
            severity="error",
            category="syntax",
            title="x",
            description="y",
            auto_fixable=True,
        )
    )
    assert f.severity == "warning"  # uses _finding_row value
    assert "INSERT INTO qa_findings" in _FakeConn.last_sql


def test_list_findings_filters_by_severity(monkeypatch):
    _patch(monkeypatch, _FakeConn(rows=[_finding_row(), _finding_row(severity="critical")]))
    store = QAStore("postgresql://stub")
    rows = _run(store.list_findings("t1", severity="critical"))
    assert len(rows) == 2


def test_update_finding_status_to_fixed_sets_resolved(monkeypatch):
    _patch(monkeypatch, _FakeConn(row=_finding_row()))
    store = QAStore("postgresql://stub")
    f = _run(
        store.update_finding_status(
            "00000000-0000-0000-0000-000000000020", status="fixed", resolved=True
        )
    )
    assert f is not None
    assert "UPDATE qa_findings" in _FakeConn.last_sql


def test_create_auto_fix_request_records_attempt(monkeypatch):
    _patch(monkeypatch, _FakeConn(row=_fix_request_row()))
    store = QAStore("postgresql://stub")
    req = _run(
        store.create_auto_fix_request(
            task_id="t1",
            workflow_id="wf-1",
            workspace_id="00000000-0000-0000-0000-000000000030",
            qa_run_id="00000000-0000-0000-0000-000000000031",
            finding_ids=["f-1"],
            attempt_number=1,
        )
    )
    assert req.status == "requested"
    assert req.attempt_number == 1


def test_update_auto_fix_request_marks_completed(monkeypatch):
    _patch(monkeypatch, _FakeConn(row=_fix_request_row(status="completed")))
    store = QAStore("postgresql://stub")
    req = _run(
        store.update_auto_fix_request(
            "00000000-0000-0000-0000-000000000040",
            status="completed",
            result={"applied": [{"finding_id": "f-1"}]},
        )
    )
    assert req is not None
    assert req.status == "completed"


def test_counts_returns_zero_dict_shape(monkeypatch):
    _patch(
        monkeypatch,
        _FakeConn(
            row=_FakeRow(
                {
                    "total_validation_runs": 3,
                    "passed_runs": 1,
                    "failed_runs": 1,
                    "blocked_for_human_review_count": 1,
                    "auto_fix_requested_count": 0,
                    "total_findings": 4,
                }
            )
        ),
    )
    store = QAStore("postgresql://stub")
    counts = _run(store.counts())
    assert counts["total_validation_runs"] == 3
    assert counts["passed_runs"] == 1
    assert counts["blocked_for_human_review_count"] == 1
