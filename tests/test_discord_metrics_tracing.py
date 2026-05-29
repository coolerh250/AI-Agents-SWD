"""Discord-gateway must register its Prometheus counters and tracing helpers."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def test_discord_metrics_module_exposes_series():
    from shared.sdk.observability.metrics import (
        DISCORD_INTAKE_FAILURES_TOTAL,
        DISCORD_MESSAGES_RECEIVED_TOTAL,
        DISCORD_NOTIFICATIONS_PUBLISHED_TOTAL,
        DISCORD_REQUEST_DURATION_SECONDS,
        DISCORD_TASKS_DISPATCHED_TOTAL,
    )

    # Touching .labels(...) registers a series; .inc(0) leaves the value at 0.
    DISCORD_MESSAGES_RECEIVED_TOTAL.labels(command_type="slash", sandbox="true").inc(0)
    DISCORD_TASKS_DISPATCHED_TOTAL.labels(command_type="slash", result="ok", sandbox="true").inc(0)
    DISCORD_INTAKE_FAILURES_TOTAL.labels(reason="parse_error").inc(0)
    DISCORD_NOTIFICATIONS_PUBLISHED_TOTAL.labels(
        event_type="discord.task.received", sandbox="true"
    ).inc(0)
    DISCORD_REQUEST_DURATION_SECONDS.labels(endpoint="/discord/messages").observe(0.001)


def _load_main() -> ModuleType:
    src = Path(__file__).resolve().parents[1] / "apps" / "discord-gateway" / "src"
    sys.path.insert(0, str(src))
    try:
        for name in ("parser", "client"):
            spec = importlib.util.spec_from_file_location(name, src / f"{name}.py")
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
        main_spec = importlib.util.spec_from_file_location(
            "discord_gateway_main_metrics", src / "main.py"
        )
        assert main_spec is not None and main_spec.loader is not None
        main_module = importlib.util.module_from_spec(main_spec)
        main_spec.loader.exec_module(main_module)
        return main_module
    finally:
        if str(src) in sys.path:
            sys.path.remove(str(src))


def test_metrics_endpoint_exposes_discord_series():
    """Service /metrics route must enumerate the discord_* counters by HELP/TYPE."""
    from fastapi.testclient import TestClient

    module = _load_main()
    client = TestClient(module.app)
    response = client.get("/metrics")
    assert response.status_code == 200
    body = response.text
    for series in (
        "discord_messages_received_total",
        "discord_tasks_dispatched_total",
        "discord_intake_failures_total",
        "discord_notifications_published_total",
        "discord_request_duration_seconds",
    ):
        assert series in body, series


def test_client_module_refuses_real_call_without_token(monkeypatch):
    src = Path(__file__).resolve().parents[1] / "apps" / "discord-gateway" / "src"
    sys.path.insert(0, str(src))
    try:
        spec = importlib.util.spec_from_file_location("discord_gateway_client", src / "client.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        if str(src) in sys.path:
            sys.path.remove(str(src))
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    monkeypatch.delenv("RUN_REAL_DISCORD_TEST", raising=False)
    client = module.DiscordClient()
    assert client.has_token is False
    assert client.real_test_enabled is False
    assert client.can_make_real_call() is False
