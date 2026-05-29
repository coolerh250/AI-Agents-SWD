"""orchestrator /operations endpoints must surface notification delivery state."""

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
            "orchestrator_operations_notif", _ORCH_SRC / "operations.py"
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
def operations_module(monkeypatch):
    module = _load_operations()

    async def _scalar(sql: str, *params: Any) -> int:
        if "production_executed" in sql or "environment='production'" in sql:
            return 0
        return 0

    async def _xinfo(bus, stream):
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
        if "/api/v2/receivers" in url:
            return 200, [{"name": "null-receiver"}]
        return 200, {"service": "ok"}

    class _FakeDeliveryStore:
        async def counts(self, **kwargs: Any) -> dict[str, int]:
            return {
                "total": 10,
                "simulated": 9,
                "delivered": 1,
                "failed": 0,
                "skipped": 0,
                "external_sent": 1,
            }

        async def list_deliveries(self, **kwargs: Any) -> list[dict[str, Any]]:
            return [
                {
                    "delivery_id": "d1",
                    "task_id": kwargs.get("task_id"),
                    "event_type": "discord.task.completed",
                    "channel": "discord",
                    "target": "sandbox",
                    "status": "simulated",
                    "sandbox": True,
                    "external_sent": False,
                    "message_id": None,
                    "error": None,
                    "source_message_id": "1-0",
                    "metadata": {},
                    "created_at": "2026-05-29T01:00:00+00:00",
                    "delivered_at": None,
                },
            ]

    monkeypatch.setattr(module, "_scalar", _scalar)
    monkeypatch.setattr(module, "_xinfo_stream", _xinfo)
    monkeypatch.setattr(module, "_http_get", _http_get)
    monkeypatch.setattr(module, "NotificationDeliveryStore", lambda: _FakeDeliveryStore())
    return module


def test_summary_includes_notification_delivery(operations_module):
    client = _client(operations_module)
    response = client.get("/operations/summary")
    assert response.status_code == 200
    body = response.json()
    assert "notification_delivery_summary" in body
    nd = body["notification_delivery_summary"]
    assert nd["total_deliveries"] == 10
    assert nd["simulated_deliveries"] == 9
    assert nd["external_sent_deliveries"] == 1
    assert nd["failed_deliveries"] == 0


def test_safety_includes_discord_fields(operations_module, monkeypatch):
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    monkeypatch.delenv("DISCORD_TEST_CHANNEL_ID", raising=False)
    monkeypatch.delenv("RUN_REAL_DISCORD_TEST", raising=False)
    client = _client(operations_module)
    response = client.get("/operations/safety")
    assert response.status_code == 200
    body = response.json()
    for key in (
        "discord_has_token",
        "discord_test_channel_configured",
        "discord_real_test_enabled",
        "discord_external_send_enabled",
    ):
        assert key in body
    assert body["discord_has_token"] is False
    assert body["discord_real_test_enabled"] is False
    assert body["discord_external_send_enabled"] is False
    # Tokens are never returned in the body.
    assert "discord_bot_token" not in body
    # Result stays safe when production counts are 0 and no external send is enabled.
    assert body["result"] in ("safe", "warning")


def test_workflow_view_includes_notification_deliveries(operations_module, monkeypatch):
    module = operations_module

    class _FakeWF:
        async def get_workflow_state(self, task_id: str):
            return {
                "task_id": task_id,
                "stage": "completed",
                "request": {},
                "state": {"workflow_id": "wf-1", "execution_result": {}},
                "approval_required": False,
                "approval_status": "not_required",
                "risk_level": "low",
                "execution_result": {"production_executed": False},
                "created_at": None,
                "updated_at": None,
            }

    class _FakeExec:
        async def list_executions(self, **kwargs: Any) -> list[dict[str, Any]]:
            return []

    class _FakeAudit:
        async def get_audit_logs(self, task_id: str):
            return []

    class _FakeInc:
        async def list_incidents(self, **kwargs: Any) -> list:
            return []

    async def _dep(task_id: str) -> dict[str, Any]:
        return {}

    async def _xrev(bus, stream, count=50):
        return []

    monkeypatch.setattr(module, "WorkflowStore", lambda: _FakeWF())
    monkeypatch.setattr(module, "AgentExecutionStore", lambda: _FakeExec())
    monkeypatch.setattr(module, "AuditStore", lambda: _FakeAudit())
    monkeypatch.setattr(module, "IncidentStore", lambda: _FakeInc())
    monkeypatch.setattr(module, "_deployment_record_for", _dep)
    monkeypatch.setattr(module, "_xrevrange_payloads", _xrev)

    client = _client(module)
    response = client.get("/operations/workflows/t-1")
    assert response.status_code == 200
    body = response.json()
    assert "notification_deliveries" in body
    nd = body["notification_deliveries"]
    assert nd["count"] == 1
    assert nd["simulated_count"] == 1
    assert nd["external_sent_count"] == 0
    assert nd["latest_status"] == "simulated"


def test_safety_marks_warning_when_discord_external_enabled(monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "x")
    monkeypatch.setenv("DISCORD_TEST_CHANNEL_ID", "y")
    monkeypatch.setenv("RUN_REAL_DISCORD_TEST", "true")
    module = _load_operations()

    async def _scalar(sql: str, *params: Any) -> int:
        return 0

    async def _http_get(url: str, timeout: float = 3.0):
        if "/api/v2/receivers" in url:
            return 200, [{"name": "null-receiver"}]
        return 200, {}

    monkeypatch.setattr(module, "_scalar", _scalar)
    monkeypatch.setattr(module, "_http_get", _http_get)
    client = _client(module)
    response = client.get("/operations/safety")
    assert response.status_code == 200
    body = response.json()
    assert body["discord_external_send_enabled"] is True
    assert body["result"] == "warning"
    assert any("discord_external_send_enabled" in w for w in body["warnings"])
