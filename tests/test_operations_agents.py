"""Tests for /operations/agents and /operations/agents/{agent_name}."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from fastapi.testclient import TestClient

_ORCH_SRC = Path(__file__).resolve().parents[1] / "apps" / "orchestrator" / "src"


def _load() -> ModuleType:
    sys.path.insert(0, str(_ORCH_SRC))
    try:
        spec = importlib.util.spec_from_file_location(
            "orchestrator_operations_agents", _ORCH_SRC / "operations.py"
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


@pytest.fixture
def agents_module(monkeypatch):
    module = _load()

    async def _http_get(url: str, timeout: float = 3.0):
        if url.endswith("/status"):
            return 200, {
                "processed_count": 5,
                "failed_count": 0,
                "last_task_id": "t1",
                "last_error": None,
            }
        return 200, {"status": "ok"}

    async def _scalar(sql: str, *params: Any) -> int:
        if "failed" in sql:
            return 1
        return 4

    async def _xinfo_stream(bus, stream):
        return {
            "name": stream,
            "length": 0,
            "groups": [],
            "consumers": 1,
            "pending": 0,
            "lag": 0,
            "last_delivered_id": "1-1",
            "status": "ok",
        }

    class _FakeExecStore:
        async def list_executions(self, **_kw: Any) -> list[dict]:
            return [{"agent": "intake-agent", "status": "completed"}]

    class _FakeAuditStore:
        async def list_audit_logs(self, **_kw: Any) -> list[dict]:
            return [{"decision_type": "intake", "agent": "intake-agent"}]

    monkeypatch.setattr(module, "_http_get", _http_get)
    monkeypatch.setattr(module, "_scalar", _scalar)
    monkeypatch.setattr(module, "_xinfo_stream", _xinfo_stream)
    monkeypatch.setattr(module, "AgentExecutionStore", lambda: _FakeExecStore())
    monkeypatch.setattr(module, "AuditStore", lambda: _FakeAuditStore())
    return module


def test_operations_agents_lists_pipeline(agents_module):
    client = _client(agents_module)
    response = client.get("/operations/agents")
    assert response.status_code == 200
    body = response.json()
    names = [agent["name"] for agent in body["agents"]]
    assert names == [
        "intake-agent",
        "requirement-agent",
        "development-agent",
        "qa-agent",
        "devops-agent",
    ]
    for entry in body["agents"]:
        assert entry["health_status"] == "ok"
        assert entry["processed_count"] == 5
        assert entry["recent_executions_count"] == 4
        assert entry["recent_failures_count"] == 1
        assert entry["input_stream"]
        assert entry["output_stream"]
        assert entry["consumer_group"]


def test_operations_agent_detail_for_known_agent(agents_module):
    client = _client(agents_module)
    response = client.get("/operations/agents/intake-agent")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "intake-agent"
    assert "recent_executions" in body
    assert "recent_audit_events" in body
    assert body["stream_info"]["consumers"] == 1


def test_operations_agent_detail_404_for_unknown_agent(agents_module):
    client = _client(agents_module)
    response = client.get("/operations/agents/bogus-agent")
    assert response.status_code == 404
