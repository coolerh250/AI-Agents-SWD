"""Assert discord-gateway publishes the expected audit + notification events."""

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
            "discord_gateway_main_audit", _DG_SRC / "main.py"
        )
        assert main_spec is not None and main_spec.loader is not None
        main_module = importlib.util.module_from_spec(main_spec)
        main_spec.loader.exec_module(main_module)
        return main_module
    finally:
        if str(_DG_SRC) in sys.path:
            sys.path.remove(str(_DG_SRC))


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.status_code = 200
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        return None


class _FakeClient:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def __aenter__(self) -> "_FakeClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def post(self, url: str, json: dict[str, Any] | None = None) -> _FakeResponse:
        return _FakeResponse(
            {
                "task_id": (json or {}).get("task_id"),
                "mode": "orchestrator",
                "stage": "completed",
                "approval_required": False,
            }
        )

    async def get(self, url: str) -> _FakeResponse:
        return _FakeResponse({})


@pytest.fixture
def captured_module(monkeypatch):
    module = _load_main()
    audit_calls: list[dict[str, Any]] = []
    publish_calls: list[tuple[str, dict[str, Any]]] = []

    async def _audit(**kwargs: Any) -> str:
        audit_calls.append(kwargs)
        return "audit-id"

    monkeypatch.setattr(module, "publish_audit_event", _audit)

    class _FakeNotificationClient:
        STREAM = "stream.notifications"

        def __init__(self) -> None:
            class _Bus:
                async def publish_event(self, stream: str, event: dict[str, Any]) -> str:
                    publish_calls.append((stream, event))
                    return "1-0"

            self.event_bus = _Bus()

        async def close(self) -> None:
            return None

    monkeypatch.setattr(module, "NotificationClient", _FakeNotificationClient)

    def _factory(*args: Any, **kwargs: Any) -> _FakeClient:
        return _FakeClient()

    monkeypatch.setattr(httpx, "AsyncClient", _factory)
    return module, audit_calls, publish_calls


def test_intake_publishes_audit_and_notifications(captured_module):
    module, audit_calls, publish_calls = captured_module
    client = TestClient(module.app)
    response = client.post(
        "/discord/messages",
        json={
            "content": '/ai task type=dev.test description="audit test"',
            "channel_id": "ch-aud",
            "user_id": "u-aud",
            "message_id": "m-aud",
        },
    )
    assert response.status_code == 200
    # Audit event was published to stream.audit via the unified publisher.
    assert any(
        call.get("decision_type") == "discord_intake" and call.get("agent") == "discord-gateway"
        for call in audit_calls
    ), audit_calls
    refs = audit_calls[-1]["artifact_refs"]
    assert refs["channel_id"] == "ch-aud"
    assert refs["user_id"] == "u-aud"
    assert refs["sandbox"] is True
    assert refs["operations_url"].startswith("/operations/workflows/")
    # Notification stream received both discord.task.received and the
    # status-derived event.
    event_types = [event.get("event_type") for _stream, event in publish_calls]
    assert "discord.task.received" in event_types
    assert any(et and et.startswith("discord.task.") for et in event_types)
    for _stream, event in publish_calls:
        assert event["sandbox"] is True


def test_notify_test_publishes_test_event(captured_module):
    module, audit_calls, publish_calls = captured_module
    client = TestClient(module.app)
    response = client.post(
        "/discord/notify/test",
        json={
            "channel_id": "ch-notify",
            "user_id": "u-notify",
            "message": "hello sandbox",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["event_type"] == "discord.notification.test"
    assert body["sandbox"] is True
    assert any(
        evt.get("event_type") == "discord.notification.test" for _stream, evt in publish_calls
    )
    assert any(call.get("decision_type") == "discord_notification_test" for call in audit_calls)
