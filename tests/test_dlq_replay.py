import json
import uuid

import pytest
from fastapi.testclient import TestClient

from scheduler import RetryScheduler
from shared.sdk.event_bus.redis_streams import RedisStreamEventBus


def test_deadletter_list_endpoint_responds(retry_scheduler_module):
    client = TestClient(retry_scheduler_module.app)
    response = client.get("/deadletter")
    # 200 when Redis is reachable, 503 when it is not — both prove the route
    # is wired correctly. We never want 404 / 500 on the list endpoint.
    assert response.status_code in (200, 503)


def test_replay_unknown_message_returns_404_or_503(retry_scheduler_module):
    client = TestClient(retry_scheduler_module.app)
    response = client.post("/deadletter/replay/0-0")
    assert response.status_code in (404, 503)


async def _bus_or_skip() -> RedisStreamEventBus:
    bus = RedisStreamEventBus()
    try:
        await bus.client.ping()
    except Exception:
        await bus.close()
        pytest.skip("no reachable Redis; skipping DLQ replay integration test")
    return bus


async def test_manual_replay_publishes_back_to_original_stream():
    bus = await _bus_or_skip()
    sched = RetryScheduler(event_bus=bus)
    target = f"test.dlq.replay.{uuid.uuid4().hex}"
    task_id = f"dlq-replay-{uuid.uuid4().hex[:8]}"
    try:
        message_id = await bus.publish_dead_letter(
            target,
            {"task_id": task_id, "workflow_id": "wf-replay", "retry_count": 1, "max_retries": 3},
            "operator-triggered",
        )
        result = await sched.replay(message_id)
        assert result["replayed"] is True
        assert result["stream"] == target
        assert result["task_id"] == task_id
        entries = await bus.client.xrevrange(target, "+", "-", count=10)
        assert entries
        event = json.loads(entries[0][1]["data"])
        assert event["event"] == "retry.manual_replay"
        assert event["task_id"] == task_id
        assert event["workflow_id"] == "wf-replay"
    finally:
        await bus.client.delete(target)
        await bus.close()


async def test_manual_replay_unknown_message_raises_key_error():
    bus = await _bus_or_skip()
    sched = RetryScheduler(event_bus=bus)
    try:
        with pytest.raises(KeyError):
            await sched.replay("999999999999-0")
    finally:
        await bus.close()
