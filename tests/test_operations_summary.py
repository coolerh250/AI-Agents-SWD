"""Tests for /operations/health and /operations/summary.

We don't talk to a real Postgres or Redis here — we stub the scalar query
helper, the stream snapshot helper, the http GET helper, and the safety
counter so the route logic can be exercised offline.
"""

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
            "orchestrator_operations", _ORCH_SRC / "operations.py"
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
def operations(monkeypatch):
    module = _load_operations()

    async def _scalar(sql: str, *params: Any) -> int:
        # Deterministic small counts so the summary endpoint returns
        # something predictable.
        if "workflow_states" in sql and "stage='completed'" in sql:
            return 7
        if "workflow_states" in sql and "production_executed" in sql:
            return 0
        if "deployment_records" in sql and "production_executed" in sql:
            return 0
        if "deployment_records" in sql and "environment='production'" in sql:
            return 0
        if "workflow_states" in sql:
            return 10
        if "audit_logs" in sql and "github_pr_integration" in sql:
            return 3
        if "audit_logs" in sql and "github_automation" in sql:
            return 2
        if "audit_logs" in sql:
            return 100
        if "incident_records" in sql and "open" in sql:
            return 1
        if "incident_records" in sql and "acknowledged" in sql:
            return 0
        if "incident_records" in sql and "resolved" in sql:
            return 5
        if "agent_executions" in sql and "failed" in sql:
            return 2
        if "agent_executions" in sql and "completed" in sql:
            return 50
        if "agent_executions" in sql:
            return 55
        return 0

    async def _xinfo_stream(bus: Any, stream: str) -> dict[str, Any]:
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

    async def _http_get(url: str, timeout: float = 3.0):
        return 200, {"service": "ok", "status": "ok"}

    monkeypatch.setattr(module, "_scalar", _scalar)
    monkeypatch.setattr(module, "_xinfo_stream", _xinfo_stream)
    monkeypatch.setattr(module, "_http_get", _http_get)
    return module


def test_operations_health(operations):
    client = _client(operations)
    response = client.get("/operations/health")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "operations"
    assert body["status"] == "ok"
    assert "generated_at" in body


def test_operations_summary_returns_expected_sections(operations):
    client = _client(operations)
    response = client.get("/operations/summary")
    assert response.status_code == 200
    body = response.json()
    for section in (
        "services_summary",
        "workflows_summary",
        "agents_summary",
        "incidents_summary",
        "dlq_summary",
        "github_summary",
        "audit_summary",
        "production_safety",
    ):
        assert section in body, section
    assert body["workflows_summary"]["completed"] == 7
    # Production safety must say safe when all three counters are 0.
    assert body["production_safety"]["result"] == "safe"
    assert body["production_safety"]["deployment_records_production_executed_true"] == 0
    assert body["production_safety"]["workflow_states_production_executed_true"] == 0


def test_operations_summary_flips_unsafe_when_production_count_positive(operations, monkeypatch):
    async def _scalar(sql: str, *params: Any) -> int:
        if "production_executed" in sql:
            return 3  # unsafe
        return 0

    monkeypatch.setattr(operations, "_scalar", _scalar)
    client = _client(operations)
    response = client.get("/operations/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["production_safety"]["result"] == "unsafe"


def test_operations_summary_metrics_register():
    """The Stage 20 counters / histogram must be registered."""
    from shared.sdk.observability.metrics import (
        OPERATIONS_REQUEST_DURATION_SECONDS,
        OPERATIONS_REQUEST_FAILURES_TOTAL,
        OPERATIONS_REQUESTS_TOTAL,
    )

    # Calling .labels(...) is enough to register a series — exercise each
    # without asserting a particular value so the test is independent of
    # other tests in the same process.
    OPERATIONS_REQUESTS_TOTAL.labels(endpoint="/operations/test", result="ok").inc(0)
    OPERATIONS_REQUEST_FAILURES_TOTAL.labels(endpoint="/operations/test", reason="store_error").inc(
        0
    )
    OPERATIONS_REQUEST_DURATION_SECONDS.labels(endpoint="/operations/test").observe(0.001)
