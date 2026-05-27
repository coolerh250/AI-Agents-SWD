"""Unit tests for shared.sdk.audit.store.AuditStore.

We don't talk to a real Postgres here — we stub asyncpg.connect so the
INSERT / SELECT / dedup paths can be exercised without a database. The
contract under test is:

* write_audit_log inserts via the SQL the audit-service already uses.
* write_audit_log skips when source_message_id has already been seen.
* list_audit_logs / get_audit_logs build correct WHERE clauses.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import asyncpg

from shared.sdk.audit.store import AuditStore


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _FakeRow(dict):
    """Looks enough like asyncpg.Record for the store's row mapper."""

    def __getitem__(self, key: str) -> Any:
        return dict.__getitem__(self, key)


class _FakeConn:
    last_sql: str = ""
    last_params: tuple = ()

    def __init__(self, row: _FakeRow | None = None, rows: list[_FakeRow] | None = None) -> None:
        self._row = row
        self._rows = rows or []

    async def fetchrow(self, sql: str, *params: Any) -> _FakeRow | None:
        _FakeConn.last_sql = sql
        _FakeConn.last_params = params
        return self._row

    async def fetch(self, sql: str, *params: Any) -> list[_FakeRow]:
        _FakeConn.last_sql = sql
        _FakeConn.last_params = params
        return self._rows

    async def close(self) -> None:
        return None


def _patch_connect(monkeypatch, conn: _FakeConn) -> None:
    async def _connect(*args: Any, **kwargs: Any) -> _FakeConn:
        return conn

    monkeypatch.setattr(asyncpg, "connect", _connect)


def _make_row(task_id: str = "t1") -> _FakeRow:
    return _FakeRow(
        {
            "id": uuid4(),
            "task_id": task_id,
            "agent": "intake-agent",
            "decision_type": "intake",
            "summary": "ok",
            "result": "ok",
            "artifact_refs": {"source_message_id": "1-0"},
            "created_at": datetime.now(timezone.utc),
        }
    )


def test_write_audit_log_inserts_and_returns_row(monkeypatch):
    row = _make_row("t1")
    _patch_connect(monkeypatch, _FakeConn(row=row))
    store = AuditStore(dsn="postgresql://example")
    out = _run(
        store.write_audit_log(
            {
                "task_id": "t1",
                "agent": "intake-agent",
                "decision_type": "intake",
                "summary": "ok",
                "result": "ok",
                "artifact_refs": {"source_message_id": "1-0"},
            }
        )
    )
    assert out is not None
    assert out["task_id"] == "t1"
    assert out["agent"] == "intake-agent"
    assert "INSERT INTO audit_logs" in _FakeConn.last_sql


def test_write_audit_log_dedups_by_source_message_id(monkeypatch):
    row = _make_row("t-dup")
    _patch_connect(monkeypatch, _FakeConn(row=row))
    store = AuditStore(dsn="postgresql://example")
    event = {
        "task_id": "t-dup",
        "agent": "a",
        "decision_type": "d",
        "summary": "s",
        "result": "r",
        "artifact_refs": {"source_message_id": "same-1"},
    }
    first = _run(store.write_audit_log(event))
    second = _run(store.write_audit_log(event))
    assert first is not None
    assert second is None  # second call short-circuits by the in-memory cache


def test_write_audit_log_without_source_id_never_dedups(monkeypatch):
    row = _make_row("t-no-id")
    _patch_connect(monkeypatch, _FakeConn(row=row))
    store = AuditStore(dsn="postgresql://example")
    event = {
        "task_id": "t-no-id",
        "agent": "a",
        "decision_type": "d",
        "summary": "s",
        "result": "r",
        "artifact_refs": {},
    }
    first = _run(store.write_audit_log(event))
    second = _run(store.write_audit_log(event))
    assert first is not None
    assert second is not None  # no source_message_id -> always writes


def test_list_audit_logs_builds_where_clause(monkeypatch):
    _patch_connect(monkeypatch, _FakeConn(rows=[_make_row("t-list")]))
    store = AuditStore(dsn="postgresql://example")
    rows = _run(
        store.list_audit_logs(
            decision_type="github_pr_integration",
            agent="devops-agent",
            task_id="t-list",
            limit=5,
        )
    )
    assert len(rows) == 1
    assert "decision_type = $1" in _FakeConn.last_sql
    assert "agent = $2" in _FakeConn.last_sql
    assert "task_id = $3" in _FakeConn.last_sql
    assert _FakeConn.last_params == (
        "github_pr_integration",
        "devops-agent",
        "t-list",
        5,
    )


def test_get_audit_logs_returns_rows(monkeypatch):
    _patch_connect(monkeypatch, _FakeConn(rows=[_make_row("t-get"), _make_row("t-get")]))
    store = AuditStore(dsn="postgresql://example")
    rows = _run(store.get_audit_logs("t-get"))
    assert len(rows) == 2
    assert "WHERE task_id = $1" in _FakeConn.last_sql
