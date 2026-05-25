import json
import uuid

import pytest
from fastapi.testclient import TestClient

from scheduler import (
    DEFAULT_RETRY_DELAY_SECONDS,
    MAX_RETRY_DELAY_SECONDS,
    TERMINAL_FAILURE_STREAM,
    RetryScheduler,
)
from shared.sdk.event_bus.redis_streams import (
    DEAD_LETTER_STREAM,
    RedisStreamEventBus,
    build_dead_letter_event,
)

# === Pure unit tests ===


def test_is_terminal_when_retry_count_exceeds_max():
    sched = RetryScheduler()
    assert sched._is_terminal({"retry_count": 5, "max_retries": 3}) is True
    assert sched._is_terminal({"retry_count": 3, "max_retries": 3}) is False
    assert sched._is_terminal({"retry_count": 0}) is False


def test_retry_delay_clamps_and_defaults():
    sched = RetryScheduler()
    assert sched._retry_delay({}) == DEFAULT_RETRY_DELAY_SECONDS
    assert sched._retry_delay({"retry_after_seconds": 5.0}) == 5.0
    assert sched._retry_delay({"retry_after_seconds": 9999}) == MAX_RETRY_DELAY_SECONDS
    assert sched._retry_delay({"retry_after_seconds": -1}) == 0.0
    assert sched._retry_delay({"retry_after_seconds": "bad"}) == DEFAULT_RETRY_DELAY_SECONDS


def test_original_stream_supports_legacy_source_stream_key():
    sched = RetryScheduler()
    assert sched._original_stream({"original_stream": "s.a"}) == "s.a"
    assert sched._original_stream({"source_stream": "s.b"}) == "s.b"
    assert sched._original_stream({}) == ""


def test_build_requeue_event_keeps_correlation_ids():
    sched = RetryScheduler()
    payload = build_dead_letter_event(
        "stream.tasks",
        {"task_id": "t", "workflow_id": "wf", "retry_count": 2, "max_retries": 3},
        "boom",
    )
    event = sched._build_requeue_event(payload, "retry.requeued")
    assert event["event"] == "retry.requeued"
    assert event["task_id"] == "t"
    assert event["workflow_id"] == "wf"
    assert event["retry_count"] == 2
    assert event["original_stream"] == "stream.tasks"


def test_build_terminal_event_marks_terminal_failure():
    sched = RetryScheduler()
    payload = build_dead_letter_event(
        "stream.tasks",
        {"task_id": "t", "retry_count": 5, "max_retries": 3},
        "boom",
    )
    event = sched._build_terminal_event(payload, "1-0")
    assert event["event"] == "retry.terminal_failure"
    assert event["terminal_failure"] is True
    assert event["original_message_id"] == "1-0"
    assert event["original_stream"] == "stream.tasks"
    assert event["retry_count"] == 5


# === FastAPI endpoint tests (no Redis required for these) ===


def test_health(retry_scheduler_module):
    client = TestClient(retry_scheduler_module.app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"service": "retry-scheduler", "status": "ok"}


def test_status(retry_scheduler_module):
    client = TestClient(retry_scheduler_module.app)
    response = client.get("/status")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "retry-scheduler"
    assert body["input_stream"] == DEAD_LETTER_STREAM


# === Redis integration tests ===


async def _bus_or_skip() -> RedisStreamEventBus:
    bus = RedisStreamEventBus()
    try:
        await bus.client.ping()
    except Exception:
        await bus.close()
        pytest.skip("no reachable Redis; skipping retry scheduler integration test")
    return bus


async def test_handle_requeues_event_to_original_stream():
    bus = await _bus_or_skip()
    sched = RetryScheduler(event_bus=bus)
    target = f"test.retry.requeue.{uuid.uuid4().hex}"
    task_id = f"retry-{uuid.uuid4().hex[:8]}"
    payload = build_dead_letter_event(
        target,
        {"task_id": task_id, "workflow_id": "wf-r", "retry_count": 1, "max_retries": 3},
        "boom",
        retry_after_seconds=0.0,
    )
    try:
        result = await sched.handle("1-0", payload)
        assert result["action"] == "requeued"
        assert result["stream"] == target
        entries = await bus.client.xrevrange(target, "+", "-", count=10)
        assert entries
        event = json.loads(entries[0][1]["data"])
        assert event["event"] == "retry.requeued"
        assert event["task_id"] == task_id
        assert event["retry_count"] == 1
        assert sched.requeued_count == 1
    finally:
        await bus.client.delete(target)
        await bus.close()


async def test_handle_marks_terminal_when_retries_exhausted():
    bus = await _bus_or_skip()
    sched = RetryScheduler(event_bus=bus)
    task_id = f"term-{uuid.uuid4().hex[:8]}"
    payload = build_dead_letter_event(
        "stream.test.terminal",
        {"task_id": task_id, "retry_count": 5, "max_retries": 3},
        "boom",
    )
    try:
        before = await bus.client.xlen(TERMINAL_FAILURE_STREAM)
        result = await sched.handle("2-0", payload)
        after = await bus.client.xlen(TERMINAL_FAILURE_STREAM)
        assert result["action"] == "terminal_failure"
        assert after == before + 1
        assert sched.terminal_count == 1
    finally:
        await bus.close()


async def test_list_dead_letters_returns_published_entry():
    bus = await _bus_or_skip()
    sched = RetryScheduler(event_bus=bus)
    task_id = f"dl-list-{uuid.uuid4().hex[:8]}"
    try:
        await bus.publish_dead_letter("stream.test.list", {"task_id": task_id}, "list test")
        entries = await sched.list_dead_letters(count=100)
        matched = [e for e in entries if e["payload"].get("task_id") == task_id]
        assert matched, "the freshly-published dead-letter entry was not returned"
    finally:
        await bus.close()
