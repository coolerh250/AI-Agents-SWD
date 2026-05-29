"""notification-worker must register its Prometheus counters and tracing helpers."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def test_notification_worker_metrics_register():
    from shared.sdk.observability.metrics import (
        NOTIFICATION_WORKER_DELIVERED_TOTAL,
        NOTIFICATION_WORKER_FAILURES_TOTAL,
        NOTIFICATION_WORKER_PROCESSED_TOTAL,
        NOTIFICATION_WORKER_PROCESSING_SECONDS,
        NOTIFICATION_WORKER_SIMULATED_TOTAL,
        NOTIFICATION_WORKER_SKIPPED_TOTAL,
    )

    NOTIFICATION_WORKER_PROCESSED_TOTAL.labels(event_type="discord.task.received").inc(0)
    NOTIFICATION_WORKER_DELIVERED_TOTAL.labels(
        event_type="discord.task.completed", channel="discord"
    ).inc(0)
    NOTIFICATION_WORKER_SIMULATED_TOTAL.labels(
        event_type="discord.task.completed", channel="discord"
    ).inc(0)
    NOTIFICATION_WORKER_FAILURES_TOTAL.labels(reason="render_error").inc(0)
    NOTIFICATION_WORKER_SKIPPED_TOTAL.labels(reason="duplicate").inc(0)
    NOTIFICATION_WORKER_PROCESSING_SECONDS.observe(0.001)


def _load_main() -> ModuleType:
    src = Path(__file__).resolve().parents[1] / "apps" / "notification-worker" / "src"
    sys.path.insert(0, str(src))
    try:
        for name in ("discord_client", "worker"):
            spec = importlib.util.spec_from_file_location(name, src / f"{name}.py")
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
        main_spec = importlib.util.spec_from_file_location(
            "notification_worker_main_metrics", src / "main.py"
        )
        assert main_spec is not None and main_spec.loader is not None
        main_module = importlib.util.module_from_spec(main_spec)
        main_spec.loader.exec_module(main_module)
        return main_module
    finally:
        if str(src) in sys.path:
            sys.path.remove(str(src))


def test_metrics_endpoint_exposes_notification_worker_series():
    """Service /metrics route must enumerate the notification_worker_* counters."""
    from fastapi.testclient import TestClient

    module = _load_main()
    client = TestClient(module.app)
    response = client.get("/metrics")
    assert response.status_code == 200
    body = response.text
    for series in (
        "notification_worker_processed_total",
        "notification_worker_delivered_total",
        "notification_worker_simulated_total",
        "notification_worker_failures_total",
        "notification_worker_skipped_total",
        "notification_worker_processing_seconds",
    ):
        assert series in body, series
