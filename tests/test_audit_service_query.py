"""Unit tests for the audit-service query API (Stage 19).

Exercises GET /audit/events with task_id / agent / decision_type / limit
filters, plus the existing GET /audit/events/{task_id} path. asyncpg.connect
is stubbed so the test does not need a real Postgres.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import asyncpg
import pytest
from fastapi.testclient import TestClient


class _FakeRow(dict):
    def __getitem__(self, key: str) -> Any:
        return dict.__getitem__(self, key)


def _row(task_id: str, decision_type: str = "intake", agent: str = "intake-agent") -> _FakeRow:
    return _FakeRow(
        {
            "id": uuid4(),
            "task_id": task_id,
            "agent": agent,
            "decision_type": decision_type,
            "summary": "x",
            "result": "ok",
            "artifact_refs": {},
            "created_at": datetime.now(timezone.utc),
        }
    )


class _FakeConn:
    last_sql: str = ""
    last_params: tuple = ()

    def __init__(self, rows: list[_FakeRow]) -> None:
        self._rows = rows

    async def fetch(self, sql: str, *params: Any) -> list[_FakeRow]:
        _FakeConn.last_sql = sql
        _FakeConn.last_params = params
        return self._rows

    async def fetchrow(self, sql: str, *params: Any) -> _FakeRow | None:
        _FakeConn.last_sql = sql
        _FakeConn.last_params = params
        return self._rows[0] if self._rows else None

    async def close(self) -> None:
        return None


@pytest.fixture
def patched_audit_service(monkeypatch, audit_service_app):
    rows = [_row("t1"), _row("t2", "github_pr_integration", "devops-agent")]

    async def _connect(*_a: Any, **_kw: Any) -> _FakeConn:
        return _FakeConn(rows)

    monkeypatch.setattr(asyncpg, "connect", _connect)
    return TestClient(audit_service_app), rows


def test_list_events_default_limit(patched_audit_service):
    client, _rows = patched_audit_service
    response = client.get("/audit/events")
    assert response.status_code == 200
    body = response.json()
    assert "count" in body
    assert "events" in body
    assert isinstance(body["events"], list)
    assert "ORDER BY created_at DESC LIMIT" in _FakeConn.last_sql


def test_list_events_with_agent_filter(patched_audit_service):
    client, _rows = patched_audit_service
    response = client.get("/audit/events?agent=devops-agent&limit=5")
    assert response.status_code == 200
    assert _FakeConn.last_params[0] == "devops-agent"
    assert _FakeConn.last_params[-1] == 5
    assert "agent = $1" in _FakeConn.last_sql


def test_list_events_with_decision_type_filter(patched_audit_service):
    client, _rows = patched_audit_service
    response = client.get("/audit/events?decision_type=github_pr_integration")
    assert response.status_code == 200
    assert _FakeConn.last_params[0] == "github_pr_integration"
    assert "decision_type = $1" in _FakeConn.last_sql


def test_list_events_combined_filters(patched_audit_service):
    client, _rows = patched_audit_service
    response = client.get(
        "/audit/events?task_id=t1&agent=intake-agent&decision_type=intake&limit=10"
    )
    assert response.status_code == 200
    assert _FakeConn.last_params == ("t1", "intake-agent", "intake", 10)
    assert "task_id = $1" in _FakeConn.last_sql
    assert "agent = $2" in _FakeConn.last_sql
    assert "decision_type = $3" in _FakeConn.last_sql


def test_get_events_by_task_id_still_works(patched_audit_service):
    client, _rows = patched_audit_service
    response = client.get("/audit/events/some-task")
    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == "some-task"
    assert "count" in body
    assert "events" in body
