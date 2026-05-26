import asyncio
import json
import time
import uuid

import httpx
import pytest

from shared.sdk.event_bus.redis_streams import RedisStreamEventBus


def _redis_up() -> bool:
    bus = RedisStreamEventBus(redis_url="redis://localhost:6379")

    async def ping() -> bool:
        try:
            return bool(await bus.client.ping())
        finally:
            await bus.close()

    try:
        return asyncio.get_event_loop().run_until_complete(ping())
    except Exception:
        return False


requires_redis = pytest.mark.skipif(not _redis_up(), reason="redis not reachable on localhost")


def test_redis_streams_module_exposes_tracing_hook():
    # Imports must succeed even when OTel is best-effort — if the spans break
    # the module, every consumer in the pipeline stops working.
    from shared.sdk.event_bus.redis_streams import RedisStreamEventBus  # noqa: F401
    from shared.sdk.observability.tracing import start_span  # noqa: F401


@requires_redis
async def test_publish_consume_ack_still_work_with_spans():
    """The span context manager wrapping publish/consume/ack must not change
    behaviour: a published event still reads back through xreadgroup and the
    consumer can ack it.
    """
    bus = RedisStreamEventBus(redis_url="redis://localhost:6379")
    stream = f"test.trace.redis.{uuid.uuid4().hex[:8]}"
    group = "test-trace-redis-group"
    consumer = "test-trace-redis-1"
    task_id = f"trace-redis-{uuid.uuid4().hex[:8]}"
    try:
        event = {
            "event": "trace.test",
            "task_id": task_id,
            "workflow_id": "wf-trace-redis",
            "payload": "redis-tracing-smoke",
        }
        message_id = await bus.publish_event(stream, event)
        assert message_id
        deadline = time.time() + 10
        consumed: list = []
        while time.time() < deadline and not consumed:
            consumed = await bus.consume_events(stream, group, consumer, count=10, block_ms=500)
        assert consumed, "publish_event/consume_events round-trip failed"
        found = next(
            (item for item in consumed if item["event"].get("task_id") == task_id),
            None,
        )
        assert found is not None
        acked = await bus.ack_event(stream, group, found["id"])
        assert int(acked) >= 1
    finally:
        try:
            await bus.client.xgroup_destroy(stream, group)
        except Exception:
            pass
        try:
            await bus.client.delete(stream)
        finally:
            await bus.close()


@requires_redis
async def test_publish_carries_task_and_workflow_attributes():
    """publish_event must still persist the JSON envelope intact so the span
    attributes (task_id, workflow_id) and the payload stay in sync.
    """
    bus = RedisStreamEventBus(redis_url="redis://localhost:6379")
    stream = f"test.trace.redis.attrs.{uuid.uuid4().hex[:8]}"
    try:
        await bus.publish_event(
            stream,
            {
                "event": "trace.test",
                "task_id": "trace-redis-attrs",
                "workflow_id": "wf-trace-redis-attrs",
            },
        )
        entries = await bus.client.xrevrange(stream, "+", "-", count=1)
        assert entries
        _entry_id, fields = entries[0]
        decoded = json.loads(fields["data"])
        assert decoded["task_id"] == "trace-redis-attrs"
        assert decoded["workflow_id"] == "wf-trace-redis-attrs"
    finally:
        try:
            await bus.client.delete(stream)
        finally:
            await bus.close()


def _tempo_up() -> bool:
    try:
        return httpx.get("http://localhost:3200/ready", timeout=3).status_code < 500
    except Exception:
        return False


@pytest.mark.skipif(not _tempo_up(), reason="tempo not reachable on localhost:3200")
def test_tempo_search_endpoint_is_callable():
    # If Tempo is up we should be able to hit its /api/search endpoint without
    # an error — that endpoint is what verify_trace_flow.sh relies on.
    response = httpx.get("http://localhost:3200/api/search", timeout=5)
    assert response.status_code in (200, 400)
