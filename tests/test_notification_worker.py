"""Unit tests for apps/notification-worker/src/worker.NotificationWorker.

We stub the event bus, the delivery store, the audit publisher, and the
Discord client so the consumer loop can be exercised offline. The worker's
contract:

* sandbox payload → status=simulated, sandbox=true, external_sent=false,
  audit decision_type=notification_delivery.
* controlled-real mode (mocked client.can_deliver()=True) → status=delivered,
  external_sent=true, audit decision_type=discord_real_test_sent.
* duplicate source_message_id → skipped.
* Discord failure → mark_failed + audit notification_delivery_failed +
  retry/deadletter path.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

_NW_SRC = Path(__file__).resolve().parents[1] / "apps" / "notification-worker" / "src"


def _load_worker_module() -> ModuleType:
    sys.path.insert(0, str(_NW_SRC))
    try:
        for name in ("discord_client",):
            spec = importlib.util.spec_from_file_location(name, _NW_SRC / f"{name}.py")
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
        spec = importlib.util.spec_from_file_location(
            "notification_worker_worker", _NW_SRC / "worker.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
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

    async def ensure_group(self, *args: Any, **kwargs: Any) -> None:
        return None

    async def ack_event(self, *args: Any, **kwargs: Any) -> int:
        return 1

    async def consume_events(self, *args: Any, **kwargs: Any) -> list:
        return []

    async def close(self) -> None:
        return None


class _FakeStore:
    def __init__(self, *, dedup_keys: set[str] | None = None) -> None:
        self.created: list[dict[str, Any]] = []
        self.delivered_ids: list[str] = []
        self.failed_ids: list[tuple[str, str]] = []
        self._dedup_keys = dedup_keys or set()

    async def create_delivery(self, **kwargs: Any) -> dict[str, Any] | None:
        if kwargs.get("source_message_id") in self._dedup_keys:
            return None
        self.created.append(kwargs)
        return {
            "delivery_id": f"del-{len(self.created)}",
            **kwargs,
        }

    async def mark_delivered(self, delivery_id: str, **kwargs: Any) -> dict[str, Any]:
        self.delivered_ids.append(delivery_id)
        return {"delivery_id": delivery_id, **kwargs, "status": "delivered"}

    async def mark_failed(self, delivery_id: str, *, error: str) -> dict[str, Any]:
        self.failed_ids.append((delivery_id, error))
        return {"delivery_id": delivery_id, "status": "failed", "error": error}


class _SandboxClient:
    has_token = False
    has_test_channel = False
    real_enabled = False
    test_channel_id = ""

    def can_deliver(self) -> bool:
        return False


class _ControlledClient:
    has_token = True
    has_test_channel = True
    real_enabled = True
    test_channel_id = "1234567890"

    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail
        self.sent_messages: list[str] = []

    def can_deliver(self) -> bool:
        return True

    async def send_test_message(self, content: str) -> dict[str, Any]:
        if self._fail:
            raise RuntimeError("discord boom")
        self.sent_messages.append(content)
        return {"message_id": "discord-msg-1", "channel_id": self.test_channel_id}


def _make_worker(
    *, client, store=None
) -> tuple[ModuleType, Any, _FakeBus, Any, list[dict[str, Any]]]:
    module = _load_worker_module()
    bus = _FakeBus()
    store = store or _FakeStore()
    audit_calls: list[dict[str, Any]] = []

    async def _audit(**kwargs: Any) -> str:
        audit_calls.append(kwargs)
        return "audit-id"

    worker = module.NotificationWorker(event_bus=bus, store=store, client=client)
    # Patch the publish_audit_event used inside worker.py's namespace.
    module.publish_audit_event = _audit  # type: ignore[attr-defined]
    return module, worker, bus, store, audit_calls


def test_sandbox_handle_records_simulated_delivery():
    module, worker, bus, store, audit_calls = _make_worker(client=_SandboxClient())
    payload = {
        "task_id": "t-sb",
        "event_type": "discord.task.received",
        "message": "received",
        "sandbox": True,
    }
    outcome = _run(worker.handle("11-0", payload))
    assert outcome["action"] == "simulated"
    assert outcome["ack"] is True
    assert worker.simulated_count == 1
    assert worker.delivered_count == 0
    assert store.created[0]["sandbox"] is True
    assert store.created[0]["status"] == "simulated"
    assert store.created[0]["external_sent"] is False
    # Audit event went through Stage 19 publisher with decision_type=notification_delivery.
    assert any(
        call.get("decision_type") == "notification_delivery"
        and call.get("agent") == "notification-worker"
        for call in audit_calls
    )
    refs = audit_calls[-1]["artifact_refs"]
    assert refs["sandbox"] is True
    assert refs["external_sent"] is False
    assert refs["event_type"] == "discord.task.received"
    assert bus.published == []  # no deadletter on the happy path


def test_dedup_skips_duplicate_source_message_id():
    store = _FakeStore(dedup_keys={"dup-1"})
    module, worker, bus, store, audit_calls = _make_worker(client=_SandboxClient(), store=store)
    outcome = _run(worker.handle("dup-1", {"task_id": "t-dup", "event_type": "x"}))
    assert outcome["action"] == "skipped"
    assert outcome["reason"] == "duplicate source_message_id"
    assert worker.skipped_count == 1
    assert audit_calls == []


def test_handle_skips_non_dict_payload():
    module, worker, *_ = _make_worker(client=_SandboxClient())
    outcome = _run(worker.handle("x-0", "not-a-dict"))  # type: ignore[arg-type]
    assert outcome["action"] == "skipped"
    assert outcome["ack"] is True


def test_controlled_real_delivers_via_discord():
    client = _ControlledClient()
    module, worker, bus, store, audit_calls = _make_worker(client=client)
    payload = {
        "task_id": "t-real",
        "event_type": "discord.task.completed",
        "message": "completed",
    }
    outcome = _run(worker.handle("R-0", payload))
    assert outcome["action"] == "delivered"
    assert outcome["message_id"] == "discord-msg-1"
    assert worker.delivered_count == 1
    assert client.sent_messages and "discord.task.completed" in client.sent_messages[0]
    assert any(call.get("decision_type") == "discord_real_test_sent" for call in audit_calls)


def test_controlled_real_failure_retries_then_deadletters():
    client = _ControlledClient(fail=True)
    module, worker, bus, store, audit_calls = _make_worker(client=client)
    payload = {"task_id": "t-fail", "event_type": "discord.task.completed"}
    for _ in range(module.MAX_FAILURES_BEFORE_DEADLETTER - 1):
        outcome = _run(worker.handle("F-0", payload))
        assert outcome["action"] == "retry"
        assert outcome["ack"] is False
    outcome = _run(worker.handle("F-0", payload))
    assert outcome["action"] == "deadlettered"
    assert outcome["ack"] is True
    # Deadletter envelope went to stream.deadletter.
    assert bus.published[-1][0] == "stream.deadletter"
    envelope = bus.published[-1][1]
    assert envelope["original_stream"] == module.NOTIFICATION_STREAM
    assert envelope["original_message_id"] == "F-0"
    assert any(call.get("decision_type") == "notification_delivery_failed" for call in audit_calls)


def test_status_exposes_counters():
    module, worker, *_ = _make_worker(client=_SandboxClient())
    _run(
        worker.handle(
            "S-0",
            {"task_id": "t-s", "event_type": "discord.task.received"},
        )
    )
    status = worker.status()
    assert status["service"] == "notification-worker"
    assert status["input_stream"] == "stream.notifications"
    assert status["group"] == "notification-worker-group"
    assert status["mode"] == "sandbox"
    assert status["simulated_count"] == 1
    assert status["external_send_enabled"] is False


def test_render_discord_message_never_dumps_full_payload():
    module = _load_worker_module()
    rendered = module.render_discord_message(
        {
            "task_id": "t",
            "event_type": "discord.task.completed",
            "message": "hi",
            "status": "ok",
            "github": {"pr_url": "https://example/x/y/pull/1"},
            "secret": "should-not-appear",  # noqa: S106 - test fixture only
        }
    )
    assert "secret" not in rendered
    assert "should-not-appear" not in rendered
    assert "[discord.task.completed]" in rendered
    assert "production_executed=false" in rendered
    assert "pr=" in rendered
