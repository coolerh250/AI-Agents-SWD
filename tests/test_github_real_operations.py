"""Stage 23 operations API tests.

Covers the four ``github_*`` booleans on ``/operations/safety`` and
the ``real_test`` section on ``/operations/github/{task_id}``. No
real GitHub call is made; every external dependency is stubbed.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

_ORCH_SRC = Path(__file__).resolve().parents[1] / "apps" / "orchestrator" / "src"


def _load() -> ModuleType:
    sys.path.insert(0, str(_ORCH_SRC))
    try:
        spec = importlib.util.spec_from_file_location(
            "orchestrator_operations_real_github", _ORCH_SRC / "operations.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if str(_ORCH_SRC) in sys.path:
            sys.path.remove(str(_ORCH_SRC))


def _client(module: ModuleType) -> TestClient:
    app = FastAPI()
    app.include_router(module.router)
    return TestClient(app)


@pytest.fixture
def ops_module(monkeypatch):
    module = _load()

    async def _scalar(sql: str, *params: Any) -> int:
        return 0

    async def _http_get(url: str, timeout: float = 3.0):
        if "/api/v2/receivers" in url:
            return 200, [{"name": "null"}]
        return 200, {}

    monkeypatch.setattr(module, "_scalar", _scalar)
    monkeypatch.setattr(module, "_http_get", _http_get)
    return module


def test_safety_exposes_github_real_test_booleans(ops_module, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("RUN_REAL_GITHUB_TEST", raising=False)
    monkeypatch.delenv("GITHUB_TEST_REPO", raising=False)
    client = _client(ops_module)
    response = client.get("/operations/safety")
    assert response.status_code == 200
    body = response.json()
    for key in (
        "github_has_token",
        "github_default_dry_run",
        "real_github_test_enabled",
        "github_test_repo_configured",
        "github_external_write_enabled",
    ):
        assert key in body, f"missing {key} from /operations/safety"
    assert body["github_has_token"] is False
    assert body["real_github_test_enabled"] is False
    assert body["github_test_repo_configured"] is False
    assert body["github_external_write_enabled"] is False
    # Token value never appears in the response shape.
    assert "github_token" not in body


def test_safety_external_write_warning_when_all_three_present(ops_module, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "x")
    monkeypatch.setenv("RUN_REAL_GITHUB_TEST", "true")
    monkeypatch.setenv("GITHUB_TEST_REPO", "owner/repo")
    client = _client(ops_module)
    body = client.get("/operations/safety").json()
    assert body["github_external_write_enabled"] is True
    assert body["result"] == "warning"
    assert any("github_external_write_enabled" in w for w in body["warnings"])
    # Even with the token in the env, the response must not echo it.
    assert (
        "x" not in body.get("warnings", [None])[0]
        or "github_external_write_enabled" in body["warnings"][0]
    )


def test_operations_github_surfaces_blocked_event(ops_module, monkeypatch):
    """/operations/github/{task_id} carries a ``real_test.latest_blocked``
    section once an audit row with decision_type=github_real_test_blocked
    has been persisted.
    """

    async def _fake_workflow(self, task_id: str) -> dict[str, Any] | None:  # noqa: ARG001
        return None

    async def _fake_deploy(task_id: str) -> dict[str, Any]:  # noqa: ARG001
        return {}

    async def _fake_audit(self, task_id: str) -> list[dict[str, Any]]:  # noqa: ARG001
        return [
            {
                "decision_type": "github_real_test_blocked",
                "agent": "github-automation",
                "summary": "real GitHub test blocked at safety guard: repo_mismatch",
                "artifact_refs": {
                    "repo": "wrong/repo",
                    "reason": "repo_mismatch",
                    "dry_run": False,
                    "real_github_test": True,
                    "production_executed": False,
                    "details": {"expected": "right/repo", "received": "wrong/repo"},
                },
                "created_at": "2026-01-01T00:00:00Z",
            }
        ]

    monkeypatch.setattr(ops_module.WorkflowStore, "get_workflow_state", _fake_workflow)
    monkeypatch.setattr(ops_module, "_deployment_record_for", _fake_deploy)
    monkeypatch.setattr(ops_module.AuditStore, "get_audit_logs", _fake_audit)
    client = _client(ops_module)
    body = client.get("/operations/github/test-1").json()
    assert body["found"] is True
    assert body["real_test"]["found"] is True
    assert body["real_test"]["safety_guard_result"]["latest_blocked"]["reason"] == "repo_mismatch"
    assert body["real_test"]["production_executed"] is False


def test_operations_github_surfaces_success_event(ops_module, monkeypatch):
    async def _fake_workflow(self, task_id: str) -> dict[str, Any] | None:  # noqa: ARG001
        return None

    async def _fake_deploy(task_id: str) -> dict[str, Any]:  # noqa: ARG001
        return {}

    async def _fake_audit(self, task_id: str) -> list[dict[str, Any]]:  # noqa: ARG001
        return [
            {
                "decision_type": "github_real_test",
                "agent": "github-automation",
                "summary": "real GitHub test completed",
                "artifact_refs": {
                    "repo": "owner/repo",
                    "branch": "ai-agents-test/t",
                    "pr_url": "https://github.com/owner/repo/pull/42",
                    "issue_url": "https://github.com/owner/repo/issues/41",
                    "checks_status": "completed",
                    "dry_run": False,
                    "real_github_test": True,
                    "production_executed": False,
                },
                "created_at": "2026-01-01T00:00:00Z",
            }
        ]

    monkeypatch.setattr(ops_module.WorkflowStore, "get_workflow_state", _fake_workflow)
    monkeypatch.setattr(ops_module, "_deployment_record_for", _fake_deploy)
    monkeypatch.setattr(ops_module.AuditStore, "get_audit_logs", _fake_audit)
    client = _client(ops_module)
    body = client.get("/operations/github/test-2").json()
    assert body["real_test"]["found"] is True
    assert (
        body["real_test"]["safety_guard_result"]["latest_success"]["pr_url"]
        == "https://github.com/owner/repo/pull/42"
    )
    assert body["real_test"]["dry_run"] is False
    assert body["real_test"]["production_executed"] is False
