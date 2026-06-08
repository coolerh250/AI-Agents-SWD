"""Stage 33 -- notification-worker stream-consumer filtering tests.

These exercise the worker's ``handle()`` method end-to-end in two
mocked modes:

* the client is a controlled-real stub (``can_deliver=True``) so the
  policy is the only thing standing between an internal stream event
  and a real Discord call;
* the client is a sandbox stub for the simulated-baseline behaviour.

We assert that workflow.* / qa.* / code.* / github.* never reach the
``send_test_message`` stub, while an explicit allowlist event does.
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
            "notification_worker_worker_filter", _NW_SRC / "worker.py"
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
        self.delivered_ids: list[str] = []
        self.failed_ids: list[tuple[str, str]] = []

    async def create_delivery(self, **kwargs: Any) -> dict[str, Any] | None:
        self.created.append(kwargs)
        return {"delivery_id": f"del-{len(self.created)}", **kwargs}

    async def mark_delivered(self, delivery_id: str, **kwargs: Any) -> dict[str, Any]:
        self.delivered_ids.append(delivery_id)
        return {"delivery_id": delivery_id, **kwargs, "status": "delivered"}

    async def mark_failed(self, delivery_id: str, *, error: str) -> dict[str, Any]:
        self.failed_ids.append((delivery_id, error))
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
        return {"message_id": "real-msg-1", "channel_id": self.test_channel_id}


def _make_worker(*, policy: RealDeliveryPolicy, client=None):
    module = _load_worker_module()
    bus = _FakeBus()
    store = _FakeStore()
    audit_calls: list[dict[str, Any]] = []

    async def _audit(**kwargs: Any) -> str:
        audit_calls.append(kwargs)
        return "audit-id"

    client = client or _RealClient()
    worker = module.NotificationWorker(event_bus=bus, store=store, client=client, policy=policy)
    module.publish_audit_event = _audit  # type: ignore[attr-defined]
    return module, worker, bus, store, audit_calls, client


def _strict_policy() -> RealDeliveryPolicy:
    return RealDeliveryPolicy(
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


def test_workflow_completed_not_real_sent():
    _, worker, _, store, audit_calls, client = _make_worker(policy=_strict_policy())
    outcome = _run(
        worker.handle("M-1", {"task_id": "t", "event_type": "workflow.completed", "message": "ok"})
    )
    assert outcome["action"] == "real_blocked"
    assert client.sent == []  # never reached the real API
    assert worker.real_delivery_blocked_count == 1
    assert any(c.get("decision_type") == "discord_real_delivery_blocked" for c in audit_calls)
    # Persistence recorded the policy decision in metadata.
    meta = store.created[0]["metadata"]
    assert meta["delivery_decision"] == "real_blocked"
    assert meta["blocked_reason"] == "event_type_denied"


def test_qa_validation_passed_not_real_sent():
    _, worker, _, _, _, client = _make_worker(policy=_strict_policy())
    outcome = _run(worker.handle("M-2", {"task_id": "t", "event_type": "qa.validation_passed"}))
    assert outcome["action"] == "real_blocked"
    assert client.sent == []


def test_code_generated_not_real_sent():
    _, worker, _, _, _, client = _make_worker(policy=_strict_policy())
    outcome = _run(worker.handle("M-3", {"task_id": "t", "event_type": "code.generated"}))
    assert outcome["action"] == "real_blocked"
    assert client.sent == []


def test_github_sandbox_pr_created_not_real_sent():
    _, worker, _, _, _, client = _make_worker(policy=_strict_policy())
    outcome = _run(
        worker.handle(
            "M-4",
            {"task_id": "t", "event_type": "github.sandbox_pr.created"},
        )
    )
    assert outcome["action"] == "real_blocked"
    assert client.sent == []


def test_discord_real_test_sent_is_allowed():
    _, worker, _, store, audit_calls, client = _make_worker(policy=_strict_policy())
    outcome = _run(worker.handle("M-5", {"task_id": "t", "event_type": "discord.real_test_sent"}))
    assert outcome["action"] == "delivered"
    assert client.sent and "discord.real_test_sent" in client.sent[0]
    assert worker.real_delivery_allowed_count == 1
    assert any(c.get("decision_type") == "discord_real_test_sent" for c in audit_calls)
    meta = store.created[0]["metadata"]
    assert meta["delivery_decision"] == "real_allowed"


def test_marker_promotes_custom_event():
    _, worker, _, _, _, client = _make_worker(policy=_strict_policy())
    payload = {
        "task_id": "t",
        "event_type": "discord.custom.thing",
        "metadata": {"real_delivery": True},
    }
    outcome = _run(worker.handle("M-6", payload))
    assert outcome["action"] == "delivered"
    assert client.sent  # actually sent


def test_denylist_overrides_marker():
    _, worker, _, _, _, client = _make_worker(policy=_strict_policy())
    payload = {
        "task_id": "t",
        "event_type": "github.sandbox_pr.created",
        "metadata": {"real_delivery": True},
    }
    outcome = _run(worker.handle("M-7", payload))
    assert outcome["action"] == "real_blocked"
    assert client.sent == []


def test_blocked_event_does_not_publish_notification_loop():
    """Stage 33 contract: a blocked real delivery MUST NOT republish
    onto stream.notifications. Only stream.audit may carry the decision.
    """
    _, worker, bus, _, _, _ = _make_worker(policy=_strict_policy())
    for i in range(10):
        _run(
            worker.handle(
                f"L-{i}",
                {"task_id": "t", "event_type": "workflow.completed"},
            )
        )
    # Only deadletter would publish on the bus; blocked events must not.
    for stream, _envelope in bus.published:
        assert stream != "stream.notifications"


def test_status_exposes_policy_counters():
    _, worker, _, _, _, _ = _make_worker(policy=_strict_policy())
    _run(worker.handle("S-1", {"task_id": "t", "event_type": "workflow.completed"}))
    _run(worker.handle("S-2", {"task_id": "t", "event_type": "discord.real_test_sent"}))
    status = worker.status()
    assert status["real_delivery_enabled"] is True
    assert "discord.real_test_sent" in status["real_delivery_allowlist"]
    assert "workflow.*" in status["real_delivery_denylist"]
    assert status["real_delivery_blocked_count"] == 1
    assert status["real_delivery_allowed_count"] == 1
    assert status["last_real_delivery_decision"] == "real_allowed"
