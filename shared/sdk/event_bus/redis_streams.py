import json
import os
from datetime import datetime, timezone

import redis.asyncio as aioredis
from redis.exceptions import ResponseError

DEFAULT_REDIS_URL = "redis://localhost:6379"
DEAD_LETTER_STREAM = "stream.deadletter"
DEFAULT_MAX_RETRIES = 3


def get_retry_count(event: dict) -> int:
    """Return the retry_count carried by an event (0 when absent or invalid)."""
    try:
        return int(event.get("retry_count", 0))
    except (TypeError, ValueError):
        return 0


def get_max_retries(event: dict) -> int:
    """Return the max_retries carried by an event (DEFAULT_MAX_RETRIES when absent)."""
    try:
        return int(event.get("max_retries", DEFAULT_MAX_RETRIES))
    except (TypeError, ValueError):
        return DEFAULT_MAX_RETRIES


def with_incremented_retry(event: dict) -> dict:
    """Return a copy of an event with retry_count incremented and max_retries set."""
    updated = dict(event)
    updated["retry_count"] = get_retry_count(event) + 1
    updated["max_retries"] = get_max_retries(event)
    return updated


def is_retry_exhausted(event: dict) -> bool:
    """True when an event has reached its max_retries and must be dead-lettered."""
    return get_retry_count(event) >= get_max_retries(event)


def build_dead_letter_event(source_stream: str, event: dict, error: str = "") -> dict:
    """Wrap a failed event with the metadata needed to inspect it later."""
    return {
        "event": "deadletter",
        "task_id": event.get("task_id", "unknown"),
        "workflow_id": event.get("workflow_id", ""),
        "source_stream": source_stream,
        "error": error,
        "retry_count": get_retry_count(event),
        "max_retries": get_max_retries(event),
        "dead_lettered_at": datetime.now(timezone.utc).isoformat(),
        "original_event": event,
    }


class RedisStreamEventBus:
    """Async Redis Streams event bus for publishing and consuming events."""

    def __init__(self, redis_url: str | None = None) -> None:
        self.redis_url = redis_url or os.environ.get("REDIS_URL", DEFAULT_REDIS_URL)
        self._client: aioredis.Redis | None = None

    @property
    def client(self) -> aioredis.Redis:
        if self._client is None:
            self._client = aioredis.from_url(self.redis_url, decode_responses=True)
        return self._client

    async def ensure_group(self, stream: str, group: str) -> None:
        try:
            await self.client.xgroup_create(stream, group, id="$", mkstream=True)
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def publish_event(self, stream: str, event: dict) -> str:
        return await self.client.xadd(stream, {"data": json.dumps(event)})

    async def publish_dead_letter(self, source_stream: str, event: dict, error: str = "") -> str:
        """Publish a failed event to the dead-letter stream."""
        return await self.publish_event(
            DEAD_LETTER_STREAM, build_dead_letter_event(source_stream, event, error)
        )

    async def consume_events(
        self,
        stream: str,
        group: str,
        consumer: str,
        count: int = 10,
        block_ms: int = 5000,
    ) -> list:
        await self.ensure_group(stream, group)
        response = await self.client.xreadgroup(
            groupname=group,
            consumername=consumer,
            streams={stream: ">"},
            count=count,
            block=block_ms,
        )
        events: list = []
        for _stream, messages in response or []:
            for message_id, fields in messages:
                raw = fields.get("data", "{}")
                try:
                    payload = json.loads(raw)
                except (ValueError, TypeError):
                    payload = {"raw": raw}
                events.append({"id": message_id, "event": payload})
        return events

    async def consume_events_multi(
        self,
        streams: list[str],
        group: str,
        consumer: str,
        count: int = 10,
        block_ms: int = 5000,
    ) -> list:
        """Consume from several streams at once with one consumer group.

        Each returned event carries the ``stream`` it came from so callers can
        acknowledge it on the right stream.
        """
        for stream in streams:
            await self.ensure_group(stream, group)
        response = await self.client.xreadgroup(
            groupname=group,
            consumername=consumer,
            streams={stream: ">" for stream in streams},
            count=count,
            block=block_ms,
        )
        events: list = []
        for stream, messages in response or []:
            for message_id, fields in messages:
                raw = fields.get("data", "{}")
                try:
                    payload = json.loads(raw)
                except (ValueError, TypeError):
                    payload = {"raw": raw}
                events.append({"id": message_id, "stream": stream, "event": payload})
        return events

    async def ack_event(self, stream: str, group: str, message_id: str) -> int:
        return await self.client.xack(stream, group, message_id)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
