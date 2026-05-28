"""Tests for /operations/safety."""

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
            "orchestrator_operations_safety", _ORCH_SRC / "operations.py"
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
def safe_module(monkeypatch):
    module = _load()

    async def _scalar(sql: str, *params: Any) -> int:
        # All production counters return 0 -> safe.
        return 0

    async def _http_get(url: str, timeout: float = 3.0):
        if "/api/v2/receivers" in url:
            return 200, [{"name": "null"}]
        return 200, {}

    monkeypatch.setattr(module, "_scalar", _scalar)
    monkeypatch.setattr(module, "_http_get", _http_get)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_DRY_RUN", "true")
    monkeypatch.delenv("RUN_REAL_GITHUB_TEST", raising=False)
    return module


def test_safety_returns_safe_when_all_zero(safe_module):
    client = _client(safe_module)
    response = client.get("/operations/safety")
    assert response.status_code == 200
    body = response.json()
    assert body["result"] == "safe"
    assert body["production_executed_true_count"] == 0
    assert body["workflow_production_executed_true_count"] == 0
    assert body["external_alert_receivers_present"] is False
    assert body["github_has_token"] is False
    assert body["github_default_dry_run"] is True
    # Tokens are never leaked — only the boolean is exposed.
    assert "github_token" not in body


def test_safety_unsafe_when_production_count_positive(monkeypatch):
    module = _load()

    async def _scalar(sql: str, *params: Any) -> int:
        if "production_executed" in sql or "environment='production'" in sql:
            return 1
        return 0

    async def _http_get(url: str, timeout: float = 3.0):
        if "/api/v2/receivers" in url:
            return 200, []
        return 200, {}

    monkeypatch.setattr(module, "_scalar", _scalar)
    monkeypatch.setattr(module, "_http_get", _http_get)
    client = _client(module)
    response = client.get("/operations/safety")
    assert response.status_code == 200
    body = response.json()
    assert body["result"] == "unsafe"


def test_safety_warns_on_external_receivers(monkeypatch):
    module = _load()

    async def _scalar(sql: str, *params: Any) -> int:
        return 0

    async def _http_get(url: str, timeout: float = 3.0):
        if "/api/v2/receivers" in url:
            return 200, [{"name": "slack-prod"}, {"name": "null"}]
        return 200, {}

    monkeypatch.setattr(module, "_scalar", _scalar)
    monkeypatch.setattr(module, "_http_get", _http_get)
    client = _client(module)
    response = client.get("/operations/safety")
    assert response.status_code == 200
    body = response.json()
    assert body["external_alert_receivers_present"] is True
    assert body["result"] == "warning"
    assert any("external_alert_receivers_present" in w for w in body["warnings"])
