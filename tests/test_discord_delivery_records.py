"""discord-gateway delivery endpoints: /discord/deliveries* tests."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

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
            "discord_gateway_main_deliveries", _DG_SRC / "main.py"
        )
        assert main_spec is not None and main_spec.loader is not None
        main_module = importlib.util.module_from_spec(main_spec)
        main_spec.loader.exec_module(main_module)
        return main_module
    finally:
        if str(_DG_SRC) in sys.path:
            sys.path.remove(str(_DG_SRC))


@pytest.fixture
def deliveries_module(monkeypatch):
    module = _load_main()
    rows = [
        {
            "delivery_id": "d1",
            "task_id": "t-1",
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
        {
            "delivery_id": "d2",
            "task_id": "t-1",
            "event_type": "discord.task.received",
            "channel": "discord",
            "target": "sandbox",
            "status": "simulated",
            "sandbox": True,
            "external_sent": False,
            "message_id": None,
            "error": None,
            "source_message_id": "2-0",
            "metadata": {},
            "created_at": "2026-05-29T00:59:59+00:00",
            "delivered_at": None,
        },
    ]

    class _FakeStore:
        async def list_deliveries(self, *, task_id=None, status=None, limit=100):
            if task_id == "no-such-task":
                return []
            if status == "failed":
                return []
            return rows

    monkeypatch.setattr(module, "NotificationDeliveryStore", lambda: _FakeStore())
    return module


def test_list_deliveries_returns_all(deliveries_module):
    client = TestClient(deliveries_module.app)
    response = client.get("/discord/deliveries?limit=10")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert isinstance(body["deliveries"], list)
    assert body["deliveries"][0]["task_id"] == "t-1"


def test_list_deliveries_filtered_by_status_returns_empty(deliveries_module):
    client = TestClient(deliveries_module.app)
    response = client.get("/discord/deliveries?status=failed")
    assert response.status_code == 200
    assert response.json()["count"] == 0


def test_get_deliveries_for_task_returns_breakdown(deliveries_module):
    client = TestClient(deliveries_module.app)
    response = client.get("/discord/deliveries/t-1")
    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == "t-1"
    assert body["count"] == 2
    assert body["external_sent_count"] == 0
    assert body["simulated_count"] == 2
    assert body["failed_count"] == 0


def test_get_deliveries_for_unknown_task_returns_empty(deliveries_module):
    client = TestClient(deliveries_module.app)
    response = client.get("/discord/deliveries/no-such-task")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 0
    assert body["deliveries"] == []


def test_discord_task_lookup_includes_delivery_breakdown(monkeypatch, deliveries_module):
    module = deliveries_module
    # The lookup endpoint already gets stubbed elsewhere; here we patch the
    # operations-view fetcher so we can assert the discord-task envelope
    # surfaces the delivery fields.
    import httpx

    class _Response:
        status_code = 200
        headers = {"content-type": "application/json"}

        def json(self) -> dict[str, Any]:
            return {
                "task_id": "t-1",
                "stage": "completed",
                "execution_status": "completed",
                "approval_status": "not_required",
                "production_executed": False,
                "progress": {"completed_agents": ["intake-agent"]},
                "audit_timeline": [],
                "incidents": [],
                "github": {"pr_url": "", "dry_run": True, "status": ""},
                "trace": {"trace_id": "abc"},
            }

    class _FakeClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> "_FakeClient":
            return self

        async def __aexit__(self, *args: Any) -> None:
            return None

        async def get(self, url: str) -> _Response:
            return _Response()

    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)
    client = TestClient(module.app)
    response = client.get("/discord/tasks/t-1")
    assert response.status_code == 200
    body = response.json()
    assert body["notification_deliveries_count"] == 2
    assert body["latest_delivery_status"] == "simulated"
    assert body["delivery_breakdown"]["simulated"] == 2
    assert body["external_sent"] is False
