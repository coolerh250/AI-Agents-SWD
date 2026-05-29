"""Tests for the discord-gateway intake flow.

Stubs the httpx client used to call communication-gateway, the audit
publisher, and the NotificationClient so the test runs offline. Asserts
that a dev.test sandbox message produces the expected
``stage=completed`` envelope and that the side-effects fire.
"""

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
            "discord_gateway_main_intake", _DG_SRC / "main.py"
        )
        assert main_spec is not None and main_spec.loader is not None
        main_module = importlib.util.module_from_spec(main_spec)
        main_spec.loader.exec_module(main_module)
        return main_module
    finally:
        if str(_DG_SRC) in sys.path:
            sys.path.remove(str(_DG_SRC))


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(f"status {self.status_code}", request=None, response=None)


class _FakeClient:
    last_post: dict[str, Any] = {}

    def __init__(
        self,
        *args: Any,
        stage: str = "completed",
        approval_required: bool = False,
        **kwargs: Any,
    ) -> None:
        self._stage = stage
        self._approval_required = approval_required

    async def __aenter__(self) -> "_FakeClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def post(self, url: str, json: dict[str, Any] | None = None) -> _FakeResponse:
        _FakeClient.last_post = {"url": url, "json": json}
        body = {
            "task_id": (json or {}).get("task_id", "unknown"),
            "mode": "orchestrator",
            "stage": self._stage,
            "approval_required": self._approval_required,
            "workflow_result": {
                "task_id": (json or {}).get("task_id"),
                "stage": self._stage,
                "approval_status": ("pending" if self._approval_required else "not_required"),
            },
        }
        return _FakeResponse(200, body)

    async def get(self, url: str) -> _FakeResponse:
        return _FakeResponse(404, {})


def _patch_module(monkeypatch, module: ModuleType, *, stage: str, approval_required: bool):
    def _factory(*args: Any, **kwargs: Any) -> _FakeClient:
        return _FakeClient(stage=stage, approval_required=approval_required)

    monkeypatch.setattr(httpx, "AsyncClient", _factory)

    async def _audit(**_kwargs: Any) -> str:
        return "audit-id"

    async def _publish(stream: str, event: dict[str, Any]) -> str:
        return "notif-id"

    monkeypatch.setattr(module, "publish_audit_event", _audit)

    class _FakeNotificationClient:
        STREAM = "stream.notifications"

        def __init__(self) -> None:
            class _Bus:
                async def publish_event(self, stream: str, event: dict[str, Any]) -> str:
                    return "1-0"

            self.event_bus = _Bus()

        async def close(self) -> None:
            return None

    monkeypatch.setattr(module, "NotificationClient", _FakeNotificationClient)
    return module


@pytest.fixture
def dispatched_module(monkeypatch):
    module = _load_main()
    return _patch_module(monkeypatch, module, stage="completed", approval_required=False)


def test_post_message_dev_test_dispatches_completed(dispatched_module):
    client = TestClient(dispatched_module.app)
    response = client.post(
        "/discord/messages",
        json={
            "content": '/ai task type=dev.test description="ops smoke" github.enabled=true',
            "channel_id": "ch-int-1",
            "user_id": "u-int-1",
            "message_id": "m-int-1",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["sandbox"] is True
    assert body["request_type"] == "dev.test"
    assert body["stage"] == "completed"
    assert body["event_type"] == "discord.task.completed"
    assert body["operations_url"].startswith("/operations/workflows/")
    # The dispatch payload was posted at communication-gateway intake.
    assert "/intake/mock" in _FakeClient.last_post["url"]
    posted = _FakeClient.last_post["json"]
    assert posted["task_id"] == body["task_id"]
    assert posted["publish_to_stream"] is False
    assert posted["request"]["type"] == "dev.test"
    assert posted["request"]["discord"]["channel_id"] == "ch-int-1"


def test_post_event_mock_dispatches_completed(dispatched_module):
    client = TestClient(dispatched_module.app)
    response = client.post(
        "/discord/events/mock",
        json={
            "type": 1,
            "channel_id": "ch-mock-1",
            "author": {"id": "u-mock-1"},
            "id": "m-mock-1",
            "data": {
                "name": "ai",
                "options": [
                    {"name": "task", "value": ""},
                    {"name": "type", "value": "dev.test"},
                    {"name": "description", "value": "events-mock smoke"},
                ],
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["stage"] == "completed"
    assert body["request_type"] == "dev.test"


def test_post_message_empty_returns_400(dispatched_module):
    client = TestClient(dispatched_module.app)
    response = client.post(
        "/discord/messages",
        json={"content": "", "channel_id": "x", "user_id": "y"},
    )
    assert response.status_code == 400


def test_post_message_unsupported_returns_400(dispatched_module):
    client = TestClient(dispatched_module.app)
    response = client.post(
        "/discord/messages",
        json={"content": "hello no prefix", "channel_id": "x"},
    )
    assert response.status_code == 400
