import json
import uuid

import pytest

from shared.sdk.base_agent.stream_agent import StreamAgent
from shared.sdk.event_bus.redis_streams import (
    DEAD_LETTER_STREAM,
    DEFAULT_MAX_RETRIES,
    RedisStreamEventBus,
    build_dead_letter_event,
    get_max_retries,
    get_retry_count,
    is_retry_exhausted,
    with_incremented_retry,
)


def test_get_retry_count_defaults_to_zero():
    assert get_retry_count({}) == 0
    assert get_retry_count({"retry_count": 2}) == 2
    assert get_retry_count({"retry_count": "bad"}) == 0


def test_get_max_retries_defaults():
    assert get_max_retries({}) == DEFAULT_MAX_RETRIES
    assert get_max_retries({"max_retries": 5}) == 5


def test_with_incremented_retry_increments_without_mutating_original():
    event = {"task_id": "t", "retry_count": 1}
    bumped = with_incremented_retry(event)
    assert bumped["retry_count"] == 2
    assert bumped["max_retries"] == DEFAULT_MAX_RETRIES
    assert event["retry_count"] == 1


def test_is_retry_exhausted_threshold():
    assert is_retry_exhausted({"retry_count": 3, "max_retries": 3}) is True
    assert is_retry_exhausted({"retry_count": 2, "max_retries": 3}) is False


def test_build_dead_letter_event_wraps_original():
    original = {"task_id": "t-1", "workflow_id": "wf-1", "retry_count": 3}
    dl = build_dead_letter_event("stream.tasks", original, "boom", retry_after_seconds=2.0)
    assert dl["event"] == "deadletter"
    assert dl["task_id"] == "t-1"
    assert dl["workflow_id"] == "wf-1"
    assert dl["original_stream"] == "stream.tasks"
    assert dl["failure_reason"] == "boom"
    assert dl["retry_after_seconds"] == 2.0
    assert dl["original_event"] == original


class _FailingAgent(StreamAgent):
    name = "failing-test-agent"
    output_stream = ""
    group = "failing-test-group"
    consumer = "failing-test-1"

    async def handle(self, payload: dict) -> dict:
        raise RuntimeError("intentional test failure")


async def _bus_or_skip() -> RedisStreamEventBus:
    bus = RedisStreamEventBus()
    try:
        await bus.client.ping()
    except Exception:
        await bus.close()
        pytest.skip("no reachable Redis; skipping dead-letter integration test")
    return bus


async def test_publish_dead_letter_lands_in_dead_letter_stream():
    bus = await _bus_or_skip()
    try:
        before = await bus.client.xlen(DEAD_LETTER_STREAM)
        await bus.publish_dead_letter(
            "stream.test", {"task_id": f"dl-direct-{uuid.uuid4().hex[:8]}"}, "manual"
        )
        after = await bus.client.xlen(DEAD_LETTER_STREAM)
    finally:
        await bus.close()
    assert after == before + 1


async def test_failure_below_max_retries_is_re_enqueued():
    bus = await _bus_or_skip()
    stream = f"test.deadletter.{uuid.uuid4().hex}"
    agent = _FailingAgent(event_bus=bus)
    agent.input_stream = stream
    try:
        await agent._handle_failure({"task_id": "dl-retry", "retry_count": 0}, RuntimeError("x"))
        entries = await bus.client.xrevrange(stream, "+", "-", count=10)
        assert entries, "the failed message was not re-enqueued for retry"
        payload = json.loads(entries[0][1]["data"])
        assert payload["task_id"] == "dl-retry"
        assert payload["retry_count"] == 1
        assert agent.dead_letter_count == 0
    finally:
        await bus.client.delete(stream)
        await bus.close()


async def test_failure_at_max_retries_is_dead_lettered():
    bus = await _bus_or_skip()
    stream = f"test.deadletter.{uuid.uuid4().hex}"
    agent = _FailingAgent(event_bus=bus)
    agent.input_stream = stream
    task_id = f"dl-dead-{uuid.uuid4().hex[:8]}"
    try:
        before = await bus.client.xlen(DEAD_LETTER_STREAM)
        await agent._handle_failure(
            {"task_id": task_id, "retry_count": 2, "max_retries": 3}, RuntimeError("x")
        )
        after = await bus.client.xlen(DEAD_LETTER_STREAM)
        assert after == before + 1
        assert agent.dead_letter_count == 1
        entries = await bus.client.xrevrange(DEAD_LETTER_STREAM, "+", "-", count=100)
        matches = [
            json.loads(fields["data"])
            for _entry_id, fields in entries
            if json.loads(fields["data"]).get("task_id") == task_id
        ]
        assert matches
        assert matches[0]["event"] == "deadletter"
        assert matches[0]["retry_count"] == 3
        # an exhausted message is not re-enqueued to the input stream.
        assert await bus.client.xlen(stream) == 0
    finally:
        await bus.client.delete(stream)
        await bus.close()
