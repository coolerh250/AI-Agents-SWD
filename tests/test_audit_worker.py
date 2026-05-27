"""Unit tests for apps/audit-worker/src/worker.AuditWorker.

The worker has three responsibilities we exercise here:

* Skip the ``audit.recorded`` echo so we don't create a write loop.
* Persist normal audit events into audit_logs and ACK the message.
* Deadletter (and ACK) a message whose persist keeps failing.

Tests stub the event bus / store so we never touch Redis or Postgres.
"""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

_WORKER_PATH = Path(__file__).resolve().parents[1] / "apps" / "audit-worker" / "src" / "worker.py"


def _load_worker_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("audit_worker_worker", _WORKER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _FakeBus:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict[str, Any]]] = []
        self.acked: list[tuple[str, str, str]] = []
        self.fail_publish = False

    async def publish_event(self, stream: str, event: dict) -> str:
        if self.fail_publish:
            raise RuntimeError("redis down")
        self.published.append((stream, event))
        return "1-1"

    async def ack_event(self, stream: str, group: str, message_id: str) -> int:
        self.acked.append((stream, group, message_id))
        return 1

    async def ensure_group(self, stream: str, group: str) -> None:
        return None

    async def consume_events(self, *_a: Any, **_kw: Any) -> list:
        return []

    async def close(self) -> None:
        return None


class _FakeStore:
    def __init__(self) -> None:
        self.writes: list[dict] = []
        self.raise_n = 0

    async def write_audit_log(self, event: dict) -> dict | None:
        if self.raise_n > 0:
            self.raise_n -= 1
            raise RuntimeError("db down")
        self.writes.append(event)
        return {"audit_id": "abc", **event}


def _make_worker():
    module = _load_worker_module()
    bus = _FakeBus()
    store = _FakeStore()
    worker = module.AuditWorker(event_bus=bus, store=store)
    return module, worker, bus, store


def test_handle_persists_normal_audit_event():
    _, worker, _bus, store = _make_worker()
    payload = {
        "task_id": "t1",
        "agent": "intake-agent",
        "decision_type": "intake",
        "summary": "ok",
        "result": "ok",
        "artifact_refs": {"x": 1},
    }
    outcome = _run(worker.handle("1-0", payload))
    assert outcome["action"] == "persisted"
    assert outcome["ack"] is True
    assert worker.processed_count == 1
    assert len(store.writes) == 1
    # Provenance was added to the persisted row.
    persisted = store.writes[0]
    assert persisted["artifact_refs"]["source_message_id"] == "1-0"
    assert persisted["artifact_refs"]["source_stream"] == "stream.audit"


def test_handle_skips_audit_recorded_echo():
    _, worker, _bus, store = _make_worker()
    outcome = _run(
        worker.handle(
            "1-1",
            {"event": "audit.recorded", "task_id": "x", "audit_id": "abc"},
        )
    )
    assert outcome["action"] == "skipped"
    assert outcome["reason"] == "audit_recorded_echo"
    assert outcome["ack"] is True
    assert worker.skipped_count == 1
    assert store.writes == []  # never persisted


def test_handle_skips_non_dict_payload():
    _, worker, _bus, _store = _make_worker()
    outcome = _run(worker.handle("1-2", "not-a-dict"))  # type: ignore[arg-type]
    assert outcome["action"] == "skipped"
    assert outcome["ack"] is True
    assert worker.skipped_count == 1


def test_handle_retries_transient_db_error_then_deadletters():
    module, worker, bus, store = _make_worker()
    # Force store.write to raise repeatedly so the worker eventually deadletters.
    store.raise_n = module.MAX_FAILURES_BEFORE_DEADLETTER
    payload = {"task_id": "t-fail", "agent": "x", "decision_type": "d"}

    # First N-1 attempts must NOT ack so the consumer group re-delivers.
    for _ in range(module.MAX_FAILURES_BEFORE_DEADLETTER - 1):
        outcome = _run(worker.handle("9-9", payload))
        assert outcome["action"] == "retry"
        assert outcome["ack"] is False

    # Final attempt deadletters and acks.
    outcome = _run(worker.handle("9-9", payload))
    assert outcome["action"] == "deadlettered"
    assert outcome["ack"] is True
    # The deadletter envelope went to stream.deadletter with audit.deadlettered.
    assert bus.published, "deadletter envelope was never published"
    stream, envelope = bus.published[-1]
    assert stream == "stream.deadletter"
    assert envelope["event"] == "audit.deadlettered"
    assert envelope["original_stream"] == "stream.audit"
    assert envelope["original_message_id"] == "9-9"


def test_handle_dedups_duplicate_source_message_id():
    # Have the store return None on the second write to simulate dedup.
    module = _load_worker_module()

    class _DedupStore:
        def __init__(self) -> None:
            self.calls = 0

        async def write_audit_log(self, event: dict) -> dict | None:
            self.calls += 1
            return None if self.calls > 1 else {"audit_id": "ok", **event}

    bus = _FakeBus()
    store = _DedupStore()
    worker = module.AuditWorker(event_bus=bus, store=store)
    payload = {"task_id": "t-dup", "agent": "x", "decision_type": "d"}
    a = _run(worker.handle("dup-1", payload))
    b = _run(worker.handle("dup-1", payload))
    assert a["action"] == "persisted"
    assert b["action"] == "skipped"
    assert b["reason"] == "duplicate source_message_id"


def test_status_reflects_counters():
    _, worker, _bus, _store = _make_worker()
    _run(
        worker.handle(
            "1-0",
            {"agent": "a", "decision_type": "d", "summary": "s", "result": "r"},
        )
    )
    status = worker.status()
    assert status["service"] == "audit-worker"
    assert status["input_stream"] == "stream.audit"
    assert status["group"] == "audit-group"
    assert status["processed_count"] == 1
