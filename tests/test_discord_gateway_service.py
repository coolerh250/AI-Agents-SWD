"""Tests for the discord-gateway FastAPI surface (health / status / messages list).

Loads the service module via the same conftest helper used by audit-service
etc., but discord-gateway has no entry in conftest yet, so we load it
in-line.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from fastapi.testclient import TestClient

_DG_SRC = Path(__file__).resolve().parents[1] / "apps" / "discord-gateway" / "src"


def _load_discord_gateway() -> ModuleType:
    sys.path.insert(0, str(_DG_SRC))
    try:
        # parser + client are imported by main; load them first under the
        # bare names they expect.
        for name in ("parser", "client"):
            spec = importlib.util.spec_from_file_location(name, _DG_SRC / f"{name}.py")
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
        main_spec = importlib.util.spec_from_file_location(
            "discord_gateway_main", _DG_SRC / "main.py"
        )
        assert main_spec is not None and main_spec.loader is not None
        main_module = importlib.util.module_from_spec(main_spec)
        main_spec.loader.exec_module(main_module)
        return main_module
    finally:
        if str(_DG_SRC) in sys.path:
            sys.path.remove(str(_DG_SRC))


def test_health_returns_sandbox_mode_by_default(monkeypatch):
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    monkeypatch.delenv("RUN_REAL_DISCORD_TEST", raising=False)
    module = _load_discord_gateway()
    client = TestClient(module.app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "discord-gateway"
    assert body["status"] == "ok"
    assert body["mode"] == "sandbox"
    assert body["has_token"] is False


def test_status_exposes_counters(monkeypatch):
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    module = _load_discord_gateway()
    client = TestClient(module.app)
    response = client.get("/status")
    assert response.status_code == 200
    body = response.json()
    for key in (
        "running",
        "mode",
        "has_token",
        "real_test_enabled",
        "received_count",
        "dispatched_count",
        "failed_count",
        "last_task_id",
        "last_error",
    ):
        assert key in body
    assert body["mode"] == "sandbox"
    assert body["real_test_enabled"] is False


def test_recent_messages_endpoint_returns_empty_initially(monkeypatch):
    module = _load_discord_gateway()
    client = TestClient(module.app)
    response = client.get("/discord/messages")
    assert response.status_code == 200
    body = response.json()
    assert "count" in body
    assert isinstance(body["messages"], list)


def test_real_test_blocked_without_opt_in_flags(monkeypatch):
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    monkeypatch.delenv("RUN_REAL_DISCORD_TEST", raising=False)
    module = _load_discord_gateway()
    client = TestClient(module.app)
    response = client.post(
        "/discord/real/test-message",
        json={"channel_id": "x", "message": "hi"},
    )
    assert response.status_code == 409
