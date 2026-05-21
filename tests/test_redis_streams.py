import uuid

import pytest

from shared.sdk.event_bus.redis_streams import RedisStreamEventBus


def test_default_redis_url(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    bus = RedisStreamEventBus()
    assert bus.redis_url == "redis://localhost:6379"


def test_redis_url_from_env(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://example-host:6380")
    bus = RedisStreamEventBus()
    assert bus.redis_url == "redis://example-host:6380"


def test_explicit_redis_url_overrides_env(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://from-env:6379")
    bus = RedisStreamEventBus(redis_url="redis://explicit:6379")
    assert bus.redis_url == "redis://explicit:6379"


async def _redis_available(bus: RedisStreamEventBus) -> bool:
    try:
        await bus.client.ping()
        return True
    except Exception:
        return False


async def test_redis_integration_publish_consume_ack():
    bus = RedisStreamEventBus()
    if not await _redis_available(bus):
        await bus.close()
        pytest.skip("no reachable Redis; skipping integration test")
    stream = f"test.stream.{uuid.uuid4().hex}"
    group = "test-group"
    consumer = "test-consumer"
    try:
        await bus.ensure_group(stream, group)
        await bus.ensure_group(stream, group)  # idempotent: must not raise
        message_id = await bus.publish_event(stream, {"hello": "world"})
        assert message_id
        events = await bus.consume_events(stream, group, consumer, count=10, block_ms=1000)
        assert len(events) == 1
        assert events[0]["event"] == {"hello": "world"}
        acked = await bus.ack_event(stream, group, events[0]["id"])
        assert acked == 1
    finally:
        try:
            await bus.client.delete(stream)
        except Exception:
            pass
        await bus.close()
