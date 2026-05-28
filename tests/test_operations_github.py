"""Tests for /operations/github/{task_id}."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from fastapi.testclient import TestClient

_ORCH_SRC = Path(__file__).resolve().parents[1] / "apps" / "orchestrator" / "src"


def _load() -> ModuleType:
    sys.path.insert(0, str(_ORCH_SRC))
    try:
        spec = importlib.util.spec_from_file_location(
            "orchestrator_operations_github", _ORCH_SRC / "operations.py"
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


def _workflow_with_github() -> dict:
    return {
        "task_id": "t-gh",
        "stage": "completed",
        "state": {
            "execution_result": {
                "github": {
                    "status": "success",
                    "dry_run": True,
                    "pr_url": "https://github.com/x/y/pull/1",
                    "branch": "ai-agents/t-gh",
                    "issue_url": "https://github.com/x/y/issues/1",
                    "checks_status": "success",
                    "event_type": "github.pr.dry_run",
                }
            }
        },
        "execution_result": {},
        "approval_required": False,
        "approval_status": "not_required",
        "risk_level": "low",
        "request": {},
        "created_at": None,
        "updated_at": None,
    }


def _stub_module(monkeypatch, workflow_row, audit_rows, deployment=None):
    module = _load()

    class _WF:
        async def get_workflow_state(self, task_id: str):
            return workflow_row

    class _AS:
        async def get_audit_logs(self, task_id: str):
            return list(audit_rows)

    monkeypatch.setattr(module, "WorkflowStore", lambda: _WF())
    monkeypatch.setattr(module, "AuditStore", lambda: _AS())

    async def _dep(task_id):
        return deployment or {}

    monkeypatch.setattr(module, "_deployment_record_for", _dep)
    return module


def test_github_view_returns_workflow_github_section(monkeypatch):
    module = _stub_module(
        monkeypatch,
        workflow_row=_workflow_with_github(),
        audit_rows=[
            {
                "decision_type": "github_pr_integration",
                "agent": "devops-agent",
                "summary": "ok",
                "result": "success",
                "artifact_refs": {"pr_url": "https://github.com/x/y/pull/1"},
            }
        ],
    )
    client = _client(module)
    response = client.get("/operations/github/t-gh")
    assert response.status_code == 200
    body = response.json()
    assert body["found"] is True
    assert body["dry_run"] is True
    assert body["status"] == "success"
    assert body["pr_url"] == "https://github.com/x/y/pull/1"
    assert body["branch"] == "ai-agents/t-gh"
    assert "audit_logs" in body["source"]
    assert "workflow_states.execution_result.github" in body["source"]
    assert any(
        evt.get("decision_type") == "github_pr_integration" for evt in body["related_audit_events"]
    )


def test_github_view_returns_found_false_when_no_data(monkeypatch):
    module = _stub_module(monkeypatch, workflow_row=None, audit_rows=[])
    client = _client(module)
    response = client.get("/operations/github/no-data")
    assert response.status_code == 200
    body = response.json()
    assert body["found"] is False
    assert body["pr_url"] == ""
    assert body["related_audit_events"] == []
    assert body["source"] == []


def test_github_view_uses_deployment_metadata_when_workflow_absent(monkeypatch):
    module = _stub_module(
        monkeypatch,
        workflow_row=None,
        audit_rows=[],
        deployment={
            "metadata": {
                "github": {
                    "status": "success",
                    "dry_run": True,
                    "pr_url": "https://github.com/x/y/pull/2",
                    "branch": "ai-agents/from-dep",
                }
            }
        },
    )
    client = _client(module)
    response = client.get("/operations/github/no-workflow")
    assert response.status_code == 200
    body = response.json()
    assert body["found"] is True
    assert body["pr_url"] == "https://github.com/x/y/pull/2"
    assert "deployment_records.metadata.github" in body["source"]
