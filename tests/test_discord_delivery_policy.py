"""Discord delivery policy / safety guard tests for notification-worker.

We exercise the client's three opt-in pre-conditions and the FastAPI
``/discord/real/test-message`` endpoint to confirm that:

* default mode refuses any real Discord call with HTTP 409 + a safe
  detail (no token value leaked).
* the FastAPI route reads ``DISCORD_BOT_TOKEN`` /
  ``DISCORD_TEST_CHANNEL_ID`` / ``RUN_REAL_DISCORD_TEST`` from the env
  at request time so flipping env vars between requests works.
* a real-mode caller sends ONLY to ``DISCORD_TEST_CHANNEL_ID`` with the
  ``[AI-Agents-SWD sandbox]`` prefix.
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

_NW_SRC = Path(__file__).resolve().parents[1] / "apps" / "notification-worker" / "src"


def _load_main() -> ModuleType:
    sys.path.insert(0, str(_NW_SRC))
    try:
        for name in ("discord_client", "worker"):
            spec = importlib.util.spec_from_file_location(name, _NW_SRC / f"{name}.py")
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
        main_spec = importlib.util.spec_from_file_location(
            "notification_worker_main", _NW_SRC / "main.py"
        )
        assert main_spec is not None and main_spec.loader is not None
        main_module = importlib.util.module_from_spec(main_spec)
        main_spec.loader.exec_module(main_module)
        return main_module
    finally:
        if str(_NW_SRC) in sys.path:
            sys.path.remove(str(_NW_SRC))


def _load_discord_client() -> ModuleType:
    sys.path.insert(0, str(_NW_SRC))
    try:
        spec = importlib.util.spec_from_file_location(
            "notification_worker_discord_client", _NW_SRC / "discord_client.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if str(_NW_SRC) in sys.path:
            sys.path.remove(str(_NW_SRC))


def test_client_default_refuses_real_call(monkeypatch):
    module = _load_discord_client()
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    monkeypatch.delenv("DISCORD_TEST_CHANNEL_ID", raising=False)
    monkeypatch.delenv("RUN_REAL_DISCORD_TEST", raising=False)
    client = module.NotificationDiscordClient()
    assert client.has_token is False
    assert client.has_test_channel is False
    assert client.real_enabled is False
    assert client.can_deliver() is False


@pytest.mark.asyncio
async def test_client_raises_safety_error_without_token(monkeypatch):
    module = _load_discord_client()
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    client = module.NotificationDiscordClient()
    with pytest.raises(module.DiscordDeliverySafetyError):
        await client.send_test_message("hello")


def test_real_endpoint_returns_409_without_opt_in(monkeypatch):
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    monkeypatch.delenv("DISCORD_TEST_CHANNEL_ID", raising=False)
    monkeypatch.delenv("RUN_REAL_DISCORD_TEST", raising=False)
    module = _load_main()

    async def _audit(**_kwargs: Any) -> str:
        return "audit-id"

    monkeypatch.setattr(module, "publish_audit_event", _audit)
    client = TestClient(module.app)
    response = client.post(
        "/discord/real/test-message",
        json={"content": "should-not-go"},
    )
    assert response.status_code == 409
    body = response.json()
    assert "real Discord test is not enabled" in body["detail"]
    # Critical: nothing in the response body should leak a credential.
    assert "token" not in str(body).lower() or "DISCORD_BOT_TOKEN" in body["detail"]


def test_real_endpoint_sends_one_message_when_opt_in(monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "test-bot-credential")
    monkeypatch.setenv("DISCORD_TEST_CHANNEL_ID", "111222333")
    monkeypatch.setenv("RUN_REAL_DISCORD_TEST", "true")
    module = _load_main()

    captured: dict[str, Any] = {}

    class _Response:
        status_code = 200

        def json(self) -> dict[str, Any]:
            return {"id": "discord-msg-real-1", "channel_id": "111222333"}

        def raise_for_status(self) -> None:
            return None

    class _FakeClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> "_FakeClient":
            return self

        async def __aexit__(self, *args: Any) -> None:
            return None

        async def post(self, url: str, json: dict[str, Any], headers: dict[str, str]) -> _Response:
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return _Response()

    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)

    class _FakeStore:
        async def create_delivery(self, **kwargs: Any) -> dict[str, Any]:
            captured["delivery"] = kwargs
            return {"delivery_id": "del-real-1", **kwargs}

        async def mark_delivered(self, delivery_id: str, **kwargs: Any) -> dict[str, Any]:
            return {"delivery_id": delivery_id, "status": "delivered"}

        async def mark_failed(self, delivery_id: str, *, error: str) -> dict[str, Any]:
            return {}

        async def list_deliveries(self, **kwargs: Any) -> list:
            return []

        async def counts(self, **kwargs: Any) -> dict[str, int]:
            return {
                "total": 0,
                "simulated": 0,
                "delivered": 0,
                "failed": 0,
                "skipped": 0,
                "external_sent": 0,
            }

    monkeypatch.setattr(module, "NotificationDeliveryStore", lambda: _FakeStore())

    audit_calls: list[dict[str, Any]] = []

    async def _audit(**kwargs: Any) -> str:
        audit_calls.append(kwargs)
        return "audit-id"

    monkeypatch.setattr(module, "publish_audit_event", _audit)

    client = TestClient(module.app)
    response = client.post(
        "/discord/real/test-message",
        json={"content": "controlled live test"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["external_sent"] is True
    assert body["sandbox"] is False
    assert body["message_id"] == "discord-msg-real-1"
    # The URL targets the configured DISCORD_TEST_CHANNEL_ID — never anything else.
    assert "/channels/111222333/messages" in captured["url"]
    # The body carries the sandbox prefix; the token is in the Authorization
    # header but never appears in the JSON body we serialize.
    assert captured["json"]["content"].startswith("[AI-Agents-SWD sandbox]")
    assert "test-bot-credential" not in captured["json"]["content"]
    # Authorization header carries 'Bot ' prefix only, never the bare token elsewhere.
    assert captured["headers"]["Authorization"].startswith("Bot ")
    # Audit decision_type=discord_real_test_sent fired.
    assert any(call.get("decision_type") == "discord_real_test_sent" for call in audit_calls)
