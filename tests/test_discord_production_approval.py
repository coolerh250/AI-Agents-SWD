"""Discord-gateway must honour the workflow approval gate.

A ``production.deploy`` sandbox message must come back with
``stage=waiting_approval`` and the orchestrator's approval contract is
unchanged — production_executed is never set true by this path.
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
            "discord_gateway_main_prod", _DG_SRC / "main.py"
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
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def __aenter__(self) -> "_FakeClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def post(self, url: str, json: dict[str, Any] | None = None) -> _FakeResponse:
        return _FakeResponse(
            200,
            {
                "task_id": (json or {}).get("task_id"),
                "mode": "orchestrator",
                "stage": "waiting_approval",
                "approval_required": True,
                "workflow_result": {"stage": "waiting_approval"},
            },
        )

    async def get(self, url: str) -> _FakeResponse:
        return _FakeResponse(404, {})


@pytest.fixture
def production_module(monkeypatch):
    module = _load_main()

    def _factory(*args: Any, **kwargs: Any) -> _FakeClient:
        return _FakeClient()

    monkeypatch.setattr(httpx, "AsyncClient", _factory)

    async def _audit(**_kwargs: Any) -> str:
        return "audit-id"

    class _FakeNotificationClient:
        STREAM = "stream.notifications"

        def __init__(self) -> None:
            class _Bus:
                async def publish_event(self, stream: str, event: dict[str, Any]) -> str:
                    return "1-0"

            self.event_bus = _Bus()

        async def close(self) -> None:
            return None

    monkeypatch.setattr(module, "publish_audit_event", _audit)
    monkeypatch.setattr(module, "NotificationClient", _FakeNotificationClient)
    return module


def test_production_deploy_stops_at_waiting_approval(production_module):
    client = TestClient(production_module.app)
    response = client.post(
        "/discord/messages",
        json={
            "content": '/ai task type=production.deploy description="deploy to production"',
            "channel_id": "ch-prod",
            "user_id": "u-prod",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["stage"] == "waiting_approval"
    assert body["approval_required"] is True
    assert body["event_type"] == "discord.task.waiting_approval"
    assert body["request_type"] == "production.deploy"
    # The sandbox flag and dry_run guarantee must still be true.
    assert body["sandbox"] is True
    assert body["dry_run"] is True
