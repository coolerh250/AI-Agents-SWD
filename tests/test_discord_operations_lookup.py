"""Tests for /discord/tasks/{task_id} — the operations-view proxy."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

_DG_SRC = Path(__file__).resolve().parents[1] / "apps" / "discord-gateway" / "src"


def _load_main() -> ModuleType:
    sys.path.insert(0, str(_DG_SRC))
    try:
        for name in ("parser", "client"):
            spec = importlib.util.spec_from_file_location(name, _DG_SRC / f"{name}.py")
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
        main_spec = importlib.util.spec_from_file_location(
            "discord_gateway_main_ops", _DG_SRC / "main.py"
        )
        assert main_spec is not None and main_spec.loader is not None
        main_module = importlib.util.module_from_spec(main_spec)
        main_spec.loader.exec_module(main_module)
        return main_module
    finally:
        if str(_DG_SRC) in sys.path:
            sys.path.remove(str(_DG_SRC))


class _Response:
    def __init__(self, status_code: int, payload: dict[str, Any] | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = {"content-type": "application/json"}

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeClient:
    def __init__(self, *args: Any, response: _Response, **kwargs: Any) -> None:
        self._response = response

    async def __aenter__(self) -> "_FakeClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def get(self, url: str) -> _Response:
        return self._response


def _patch(monkeypatch, response: _Response) -> None:
    def _factory(*args: Any, **kwargs: Any) -> _FakeClient:
        return _FakeClient(response=response)

    monkeypatch.setattr(httpx, "AsyncClient", _factory)


def _operations_payload() -> dict[str, Any]:
    return {
        "task_id": "t-lookup",
        "stage": "completed",
        "execution_status": "completed",
        "approval_status": "not_required",
        "production_executed": False,
        "progress": {"completed_agents": ["intake-agent", "devops-agent"]},
        "audit_timeline": [
            {"decision_type": "intake", "agent": "intake-agent"},
            {"decision_type": "github_pr_integration", "agent": "devops-agent"},
        ],
        "incidents": [],
        "github": {
            "status": "success",
            "dry_run": True,
            "pr_url": "https://github.com/x/y/pull/1",
        },
        "trace": {"trace_id": "abc"},
    }


@pytest.fixture
def lookup_module():
    return _load_main()


def test_lookup_returns_summarized_view(monkeypatch, lookup_module):
    _patch(monkeypatch, _Response(200, _operations_payload()))
    client = TestClient(lookup_module.app)
    response = client.get("/discord/tasks/t-lookup")
    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == "t-lookup"
    assert body["stage"] == "completed"
    assert body["execution_status"] == "completed"
    assert body["completed_agents"] == ["intake-agent", "devops-agent"]
    assert body["github"]["pr_url"] == "https://github.com/x/y/pull/1"
    assert body["github"]["dry_run"] is True
    assert body["audit_timeline_count"] == 2
    assert body["incidents_count"] == 0
    assert body["production_executed"] is False
    assert body["sandbox"] is True
    assert body["operations_url"] == "/operations/workflows/t-lookup"
    # The full operations payload is also included verbatim.
    assert body["operations_view"]["stage"] == "completed"


def test_lookup_returns_404_when_operations_view_404(monkeypatch, lookup_module):
    _patch(monkeypatch, _Response(404, {}))
    client = TestClient(lookup_module.app)
    response = client.get("/discord/tasks/missing")
    assert response.status_code == 404
