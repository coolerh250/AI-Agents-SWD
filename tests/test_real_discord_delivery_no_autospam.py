"""Stage 33 -- regression test for the Step 31R autospam incident.

In Step 31R, with real Discord env live in notification-worker, the
stream consumer routed 128 events to the test channel in one hour. The
fix is the real-delivery policy: ONLY events on the explicit allowlist
(or carrying ``metadata.real_delivery=true`` AND not denied) may reach
the real Discord API. This test replays a representative burst and
asserts at most ONE message reached the real-client stub -- the single
allowlisted ``discord.real_test_sent`` event.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from shared.sdk.notifications.real_delivery_policy import RealDeliveryPolicy

_NW_SRC = Path(__file__).resolve().parents[1] / "apps" / "notification-worker" / "src"


def _load_worker_module() -> ModuleType:
    sys.path.insert(0, str(_NW_SRC))
    try:
        spec = importlib.util.spec_from_file_location(
            "discord_client", _NW_SRC / "discord_client.py"
        )
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        sys.modules["discord_client"] = mod
        spec.loader.exec_module(mod)
        spec = importlib.util.spec_from_file_location(
            "notification_worker_worker_autospam", _NW_SRC / "worker.py"
        )
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        if str(_NW_SRC) in sys.path:
            sys.path.remove(str(_NW_SRC))


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _FakeBus:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict[str, Any]]] = []

    async def publish_event(self, stream: str, event: dict[str, Any]) -> str:
        self.published.append((stream, event))
        return "dl-1"

    async def ensure_group(self, *a, **k) -> None:
        return None

    async def ack_event(self, *a, **k) -> int:
        return 1

    async def consume_events(self, *a, **k) -> list:
        return []

    async def close(self) -> None:
        return None


class _FakeStore:
    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []

    async def create_delivery(self, **kwargs: Any) -> dict[str, Any] | None:
        self.created.append(kwargs)
        return {"delivery_id": f"del-{len(self.created)}", **kwargs}

    async def mark_delivered(self, delivery_id: str, **kwargs: Any) -> dict[str, Any]:
        return {"delivery_id": delivery_id, **kwargs, "status": "delivered"}

    async def mark_failed(self, delivery_id: str, *, error: str) -> dict[str, Any]:
        return {"delivery_id": delivery_id, "status": "failed", "error": error}


class _RealClient:
    has_token = True
    has_test_channel = True
    real_enabled = True
    test_channel_id = "C-TEST"

    def __init__(self) -> None:
        self.sent: list[str] = []

    def can_deliver(self) -> bool:
        return True

    async def send_test_message(self, content: str) -> dict[str, Any]:
        self.sent.append(content)
        return {"message_id": f"real-msg-{len(self.sent)}", "channel_id": self.test_channel_id}


# 12 internal events that previously caused autospam, plus 1 allowlisted event.
_BURST = [
    {"event_type": "workflow.completed", "task_id": "t1"},
    {"event_type": "workflow.started", "task_id": "t2"},
    {"event_type": "qa.validation_passed", "task_id": "t3"},
    {"event_type": "qa.validation_failed", "task_id": "t4"},
    {"event_type": "code.generated", "task_id": "t5"},
    {"event_type": "code.review_requested", "task_id": "t6"},
    {"event_type": "github.sandbox_pr.created", "task_id": "t7"},
    {"event_type": "github.real_test_pr.created", "task_id": "t8"},
    {"event_type": "task.work_item_created", "task_id": "t9"},
    {"event_type": "llm.proposal_created", "task_id": "t10"},
    {"event_type": "approval.required", "task_id": "t11"},
    {"event_type": "incident.opened", "task_id": "t12"},
    {"event_type": "discord.real_test_sent", "task_id": "trt"},  # allowlisted
]


def _make_worker():
    module = _load_worker_module()
    bus = _FakeBus()
    store = _FakeStore()
    audit_calls: list[dict[str, Any]] = []

    async def _audit(**kwargs: Any) -> str:
        audit_calls.append(kwargs)
        return "audit-id"

    client = _RealClient()
    policy = RealDeliveryPolicy(
        real_mode_enabled=True,
        allowlist=["discord.real_test_sent", "discord.real_task_received"],
        denylist=[
            "workflow.*",
            "qa.*",
            "code.*",
            "github.*",
            "task.*",
            "llm.*",
            "approval.*",
            "audit.*",
            "incident.*",
            "retry.*",
        ],
        allow_marker=True,
        test_channel_id="C-TEST",
    )
    worker = module.NotificationWorker(event_bus=bus, store=store, client=client, policy=policy)
    module.publish_audit_event = _audit  # type: ignore[attr-defined]
    return module, worker, bus, store, audit_calls, client


def test_replay_step31r_burst_only_allowlisted_event_sent():
    _, worker, bus, store, audit_calls, client = _make_worker()
    for idx, payload in enumerate(_BURST):
        outcome = _run(worker.handle(f"burst-{idx}", payload))
        assert outcome["action"] in {"delivered", "real_blocked", "skipped"}
    # Exactly ONE message reached the real-client stub: the allowlisted
    # discord.real_test_sent.
    assert len(client.sent) == 1
    assert "discord.real_test_sent" in client.sent[0]
    # Twelve events were blocked.
    assert worker.real_delivery_blocked_count == 12
    assert worker.real_delivery_allowed_count == 1
    # Stream-publishes is limited to (potential) deadletters; no
    # notification-storm output back onto stream.notifications.
    for stream, _envelope in bus.published:
        assert stream != "stream.notifications"
    # Every blocked event got an audit row with the policy reason.
    blocked_audits = [
        c for c in audit_calls if c.get("decision_type") == "discord_real_delivery_blocked"
    ]
    assert len(blocked_audits) == 12
    for c in blocked_audits:
        refs = c["artifact_refs"]
        assert refs["sandbox"] is False
        assert refs["external_sent"] is False
        assert refs["delivery_decision"] == "real_blocked"
        assert refs["production_executed"] is False


def test_audit_storm_isolated_to_audit_stream_not_notifications():
    """Even with 50 blocked events, no recursive notification publish.

    This is the explicit "no loop" contract: the blocked-event audit
    path MUST publish only to stream.audit (via publish_audit_event,
    here stubbed) -- never back onto stream.notifications.
    """
    _, worker, bus, _store, audit_calls, _client = _make_worker()
    for i in range(50):
        _run(
            worker.handle(
                f"storm-{i}",
                {"task_id": "t", "event_type": "workflow.completed"},
            )
        )
    notif_publishes = [s for s, _ in bus.published if s == "stream.notifications"]
    assert notif_publishes == []
    # audit publish count is unbounded (via stub) but stream output is empty.
    assert len(audit_calls) >= 50
