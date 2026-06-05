"""Stage 32 -- ``/discord/real/test-message`` + ``/discord/real/events/test``
endpoint guard tests.

The endpoints are exercised via FastAPI TestClient. Real Discord is
never contacted: the guard refuses with HTTP 409 unless every
Stage 32 pre-condition is met, and the SDK guard is purely env-driven.
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
        for name in ("parser", "client"):
            spec = importlib.util.spec_from_file_location(name, _DG_SRC / f"{name}.py")
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
        main_spec = importlib.util.spec_from_file_location(
            "discord_gateway_main_real_pilot", _DG_SRC / "main.py"
        )
        assert main_spec is not None and main_spec.loader is not None
        main_module = importlib.util.module_from_spec(main_spec)
        main_spec.loader.exec_module(main_module)
        return main_module
    finally:
        if str(_DG_SRC) in sys.path:
            sys.path.remove(str(_DG_SRC))


def _client() -> TestClient:
    mod = _load_discord_gateway()
    return TestClient(mod.app)


def test_real_test_message_refused_without_env(monkeypatch):
    for k in (
        "DISCORD_BOT_TOKEN",
        "DISCORD_TEST_GUILD_ID",
        "DISCORD_TEST_CHANNEL_ID",
        "DISCORD_ALLOWED_ROLE_ID",
        "RUN_REAL_DISCORD_TEST",
    ):
        monkeypatch.delenv(k, raising=False)
    client = _client()
    resp = client.post(
        "/discord/real/test-message",
        json={"channel_id": "c1", "summary": "should not go"},
    )
    assert resp.status_code == 409
    body = resp.json()
    detail = body.get("detail")
    if isinstance(detail, dict):
        guard = detail.get("safety_guard_result", {})
        assert guard.get("allowed") is False
        # one of the known reasons
        assert guard.get("reason") in {
            "missing_discord_bot_token",
            "run_real_discord_test_not_true",
            "missing_discord_test_guild_id",
            "missing_discord_test_channel_id",
        }


def test_real_test_message_refused_wrong_channel(monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "fake-bot-token")
    monkeypatch.setenv("DISCORD_TEST_GUILD_ID", "g")
    monkeypatch.setenv("DISCORD_TEST_CHANNEL_ID", "c-allowed")
    monkeypatch.setenv("RUN_REAL_DISCORD_TEST", "true")
    monkeypatch.delenv("DISCORD_ALLOWED_ROLE_ID", raising=False)
    client = _client()
    resp = client.post(
        "/discord/real/test-message",
        json={"channel_id": "c-other", "summary": "wrong target"},
    )
    assert resp.status_code == 409
    body = resp.json()
    detail = body.get("detail", {})
    if isinstance(detail, dict):
        guard = detail.get("safety_guard_result", {})
        assert guard.get("reason") == "channel_not_test_channel"


def test_real_test_message_response_carries_no_token(monkeypatch):
    """Even the refusal path must not echo any token-shaped string."""
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "ghp_pretend_secret_value")
    monkeypatch.setenv("RUN_REAL_DISCORD_TEST", "true")
    monkeypatch.setenv("DISCORD_TEST_GUILD_ID", "g")
    monkeypatch.setenv("DISCORD_TEST_CHANNEL_ID", "c1")
    client = _client()
    resp = client.post(
        "/discord/real/test-message",
        json={"channel_id": "c-other"},
    )
    assert "ghp_pretend_secret_value" not in resp.text


def test_real_events_endpoint_refused_without_env(monkeypatch):
    for k in (
        "DISCORD_BOT_TOKEN",
        "DISCORD_TEST_GUILD_ID",
        "DISCORD_TEST_CHANNEL_ID",
        "RUN_REAL_DISCORD_TEST",
    ):
        monkeypatch.delenv(k, raising=False)
    client = _client()
    resp = client.post(
        "/discord/real/events/test",
        json={"channel_id": "c1", "content": "/ai-test task desc"},
    )
    assert resp.status_code == 409


def test_real_events_endpoint_refused_wrong_channel(monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "fake")
    monkeypatch.setenv("DISCORD_TEST_GUILD_ID", "g")
    monkeypatch.setenv("DISCORD_TEST_CHANNEL_ID", "c-allowed")
    monkeypatch.setenv("RUN_REAL_DISCORD_TEST", "true")
    client = _client()
    resp = client.post(
        "/discord/real/events/test",
        json={"channel_id": "c-other", "content": "/ai-test"},
    )
    assert resp.status_code == 409
