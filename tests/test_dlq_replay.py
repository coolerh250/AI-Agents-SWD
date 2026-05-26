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
        # The retry-scheduler container is also consuming stream.deadletter
        # in this runtime and may publish a regular ``retry.requeued`` entry
        # to the same target before/after our manual replay. Don't read the
        # newest entry — search the entries by event type so the assertion
        # is robust against that race.
        entries = await bus.client.xrange(target, "-", "+", count=50)
        replay_events = []
        for _entry_id, fields in entries:
            try:
                payload = json.loads(fields["data"])
            except (ValueError, TypeError):
                continue
            if payload.get("event") == "retry.manual_replay":
                replay_events.append(payload)
        assert replay_events, (
            "no retry.manual_replay entry found on the target stream; "
            f"entries: {[(eid, fields) for eid, fields in entries]}"
        )
        event = replay_events[-1]
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
