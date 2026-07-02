"""Step 64E.3B -- tests for the read-only /operations/agent-executions + /operations/workflows
list endpoints that the Admin Console Demo Evidence page consumes."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from fastapi import FastAPI
from fastapi.testclient import TestClient

_ORCH_SRC = Path(__file__).resolve().parents[1] / "apps" / "orchestrator" / "src"


def _load() -> ModuleType:
    sys.path.insert(0, str(_ORCH_SRC))
    try:
        spec = importlib.util.spec_from_file_location(
            "orchestrator_operations_demo_evidence", _ORCH_SRC / "operations.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if str(_ORCH_SRC) in sys.path:
            sys.path.remove(str(_ORCH_SRC))


class _FakeAgentExecutionStore:
    async def list_executions(self, task_id=None, agent=None, status=None):
        return [
            {
                "id": "e1",
                "task_id": "demo-crud-userapi",
                "agent": "intake-agent",
                "status": "completed",
                "started_at": "2026-07-01T00:00:00Z",
                "completed_at": "2026-07-01T00:00:01Z",
                "error": "should_not_be_exposed",
                "metadata": {"secret_ish": "drop"},
                "created_at": "2026-07-01T00:00:00Z",
                "updated_at": "2026-07-01T00:00:01Z",
            }
        ]


class _FakeWorkflowStore:
    async def list_workflows(self, status=None):
        return [
            {
                "task_id": "demo-crud-userapi",
                "stage": "completed",
                "request": {"drop": "large"},
                "state": {"drop": "large"},
                "approval_required": False,
                "approval_status": "not_required",
                "risk_level": "low",
                "execution_result": {"production_executed": False, "mock": True},
                "created_at": "2026-07-01T00:00:00Z",
                "updated_at": "2026-07-01T00:00:01Z",
            }
        ]


def _client(monkeypatch) -> TestClient:
    module = _load()
    monkeypatch.setattr(module, "AgentExecutionStore", _FakeAgentExecutionStore)
    monkeypatch.setattr(module, "WorkflowStore", _FakeWorkflowStore)
    app = FastAPI()
    app.include_router(module.router)
    return TestClient(app)


def test_agent_executions_shaped(monkeypatch) -> None:
    client = _client(monkeypatch)
    resp = client.get("/operations/agent-executions")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    row = body["executions"][0]
    assert row["agent"] == "intake-agent"
    assert row["status"] == "completed"
    assert row["task_id"] == "demo-crud-userapi"
    # Raw/internal fields must not be exposed.
    assert "error" not in row
    assert "metadata" not in row


def test_workflows_shaped(monkeypatch) -> None:
    client = _client(monkeypatch)
    resp = client.get("/operations/workflows")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    row = body["workflows"][0]
    assert row["task_id"] == "demo-crud-userapi"
    assert row["stage"] == "completed"
    assert row["production_executed"] is False
    # Large/internal blobs must not be exposed.
    assert "request" not in row
    assert "state" not in row
    assert "execution_result" not in row
