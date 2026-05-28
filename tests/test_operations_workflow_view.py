"""Tests for /operations/workflows/{task_id} — the unified workflow view."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from fastapi.testclient import TestClient

_ORCH_SRC = Path(__file__).resolve().parents[1] / "apps" / "orchestrator" / "src"


def _load_operations() -> ModuleType:
    sys.path.insert(0, str(_ORCH_SRC))
    try:
        spec = importlib.util.spec_from_file_location(
            "orchestrator_operations_view", _ORCH_SRC / "operations.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if str(_ORCH_SRC) in sys.path:
            sys.path.remove(str(_ORCH_SRC))


def _client(module: ModuleType) -> TestClient:
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(module.router)
    return TestClient(app)


class _FakeWorkflowStore:
    def __init__(self, row: dict | None) -> None:
        self._row = row

    async def get_workflow_state(self, task_id: str) -> dict | None:
        return self._row


class _FakeExecStore:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    async def list_executions(self, task_id: str | None = None, **_kw: Any) -> list[dict]:
        return list(self._rows)


class _FakeAuditStore:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    async def get_audit_logs(self, task_id: str) -> list[dict]:
        return list(self._rows)


class _FakeIncidentStore:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    async def list_incidents(self, **_kw: Any) -> list[Any]:
        class _Inc:
            def __init__(self, d: dict) -> None:
                self._d = d

            def to_dict(self) -> dict:
                return self._d

        return [_Inc(row) for row in self._rows]


def _stub_module(monkeypatch, *, workflow_row, executions, audit_rows, incidents):
    module = _load_operations()
    monkeypatch.setattr(module, "WorkflowStore", lambda: _FakeWorkflowStore(workflow_row))
    monkeypatch.setattr(module, "AgentExecutionStore", lambda: _FakeExecStore(executions))
    monkeypatch.setattr(module, "AuditStore", lambda: _FakeAuditStore(audit_rows))
    monkeypatch.setattr(module, "IncidentStore", lambda: _FakeIncidentStore(incidents))

    async def _xrevrange(bus, stream, count=50):
        return []

    async def _xinfo_stream(bus, stream):
        return {
            "name": stream,
            "length": 0,
            "groups": [],
            "consumers": 0,
            "pending": 0,
            "lag": 0,
            "last_delivered_id": "",
            "status": "ok",
        }

    async def _deployment(task_id):
        return {
            "deployment_record_id": "dep-1",
            "task_id": task_id,
            "environment": "test",
            "status": "simulated",
            "metadata": {
                "production_executed": False,
                "github": {
                    "status": "success",
                    "dry_run": True,
                    "pr_url": "https://github.com/x/y/pull/1",
                    "branch": "ai-agents/t1",
                },
            },
            "created_at": None,
            "updated_at": None,
        }

    monkeypatch.setattr(module, "_xrevrange_payloads", _xrevrange)
    monkeypatch.setattr(module, "_xinfo_stream", _xinfo_stream)
    monkeypatch.setattr(module, "_deployment_record_for", _deployment)
    return module


@pytest.fixture
def workflow_row():
    return {
        "task_id": "t1",
        "stage": "completed",
        "request": {},
        "state": {
            "workflow_id": "wf-1",
            "stage": "completed",
            "trace_id": "a" * 32,
            "execution_result": {
                "status": "completed",
                "production_executed": False,
                "github": {
                    "status": "success",
                    "dry_run": True,
                    "pr_url": "https://github.com/x/y/pull/1",
                    "branch": "ai-agents/t1",
                    "checks_status": "success",
                    "event_type": "github.pr.dry_run",
                },
            },
        },
        "approval_required": False,
        "approval_status": "not_required",
        "risk_level": "low",
        "execution_result": {
            "status": "completed",
            "production_executed": False,
        },
        "created_at": "2026-05-27T01:00:00+00:00",
        "updated_at": "2026-05-27T01:01:00+00:00",
    }


def test_workflow_view_returns_unified_shape(monkeypatch, workflow_row):
    module = _stub_module(
        monkeypatch,
        workflow_row=workflow_row,
        executions=[
            {
                "agent": "intake-agent",
                "status": "completed",
                "started_at": "2026-05-27T01:00:01",
                "completed_at": "2026-05-27T01:00:02",
            },
            {
                "agent": "devops-agent",
                "status": "completed",
                "started_at": "2026-05-27T01:00:30",
                "completed_at": "2026-05-27T01:00:35",
            },
        ],
        audit_rows=[
            {
                "decision_type": "github_pr_integration",
                "agent": "devops-agent",
                "created_at": "2026-05-27T01:00:36+00:00",
                "summary": "github_pr_integration",
                "result": "success",
                "artifact_refs": {"pr_url": "https://github.com/x/y/pull/1"},
            }
        ],
        incidents=[],
    )
    client = _client(module)
    response = client.get("/operations/workflows/t1")
    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == "t1"
    assert body["stage"] == "completed"
    assert body["production_executed"] is False
    assert isinstance(body["agents"], list) and len(body["agents"]) == 2
    assert isinstance(body["audit_timeline"], list) and len(body["audit_timeline"]) == 1
    assert body["audit_timeline"][0]["decision_type"] == "github_pr_integration"
    assert body["github"]["pr_url"] == "https://github.com/x/y/pull/1"
    assert body["github"]["dry_run"] is True
    assert body["github"]["status"] == "success"
    assert body["deployment"]["environment"] == "test"
    assert body["safety"]["production_executed"] is False
    assert body["trace"]["trace_id"] == "a" * 32


def test_workflow_view_returns_404_for_unknown_task(monkeypatch):
    module = _stub_module(
        monkeypatch,
        workflow_row=None,
        executions=[],
        audit_rows=[],
        incidents=[],
    )
    client = _client(module)
    response = client.get("/operations/workflows/missing-xyz")
    assert response.status_code == 404


def test_workflow_view_degrades_when_audit_store_fails(monkeypatch, workflow_row):
    module = _stub_module(
        monkeypatch,
        workflow_row=workflow_row,
        executions=[],
        audit_rows=[],
        incidents=[],
    )

    class _BoomAudit:
        async def get_audit_logs(self, task_id: str):
            raise RuntimeError("db down")

    monkeypatch.setattr(module, "AuditStore", lambda: _BoomAudit())
    client = _client(module)
    response = client.get("/operations/workflows/t1")
    assert response.status_code == 200
    body = response.json()
    assert body["audit_timeline"] == []
    assert "audit_logs_unavailable" in body["warnings"]
