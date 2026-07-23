import json
import os
from datetime import datetime, timezone

import redis.asyncio as aioredis
from redis.exceptions import ResponseError

from shared.sdk.observability.tracing import start_span

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


def build_dead_letter_event(
    original_stream: str,
    event: dict,
    failure_reason: str = "",
    retry_after_seconds: float = 0.0,
) -> dict:
    """Wrap a failed event with the metadata the retry scheduler needs."""
    return {
        "event": "deadletter",
        "task_id": event.get("task_id", "unknown"),
        "workflow_id": event.get("workflow_id", ""),
        "original_stream": original_stream,
        "failure_reason": failure_reason,
        "retry_count": get_retry_count(event),
        "max_retries": get_max_retries(event),
        "retry_after_seconds": retry_after_seconds,
        "failed_at": datetime.now(timezone.utc).isoformat(),
        "original_event": event,
    }


class RedisStreamEventBus:
    """Async Redis Streams event bus for publishing and consuming events."""

    def __init__(
        self,
        redis_url: str | None = None,
        *,
        socket_timeout: float | None = None,
        socket_connect_timeout: float | None = None,
    ) -> None:
        self.redis_url = redis_url or os.environ.get("REDIS_URL", DEFAULT_REDIS_URL)
        # Optional bounded socket timeouts. Default None preserves the existing behaviour for all
        # current callers; a caller that must never block indefinitely on a hung broker (Step
        # 66C.4-BE2-R1 outbox relay) passes bounded values so a stalled socket raises instead of
        # pinning the caller (and, for the relay, its DB transaction and row lock).
        self._socket_timeout = socket_timeout
        self._socket_connect_timeout = socket_connect_timeout
        self._client: aioredis.Redis | None = None

    @property
    def client(self) -> aioredis.Redis:
        if self._client is None:
            kwargs: dict[str, object] = {"decode_responses": True}
            if self._socket_timeout is not None:
                kwargs["socket_timeout"] = self._socket_timeout
            if self._socket_connect_timeout is not None:
                kwargs["socket_connect_timeout"] = self._socket_connect_timeout
            self._client = aioredis.from_url(self.redis_url, **kwargs)
        return self._client

    async def ensure_group(self, stream: str, group: str) -> None:
        try:
            await self.client.xgroup_create(stream, group, id="$", mkstream=True)
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def publish_event(self, stream: str, event: dict) -> str:
        with start_span(
            "redis.publish",
            **{
                "redis.stream": stream,
                "redis.operation": "xadd",
                "task_id": event.get("task_id", ""),
                "workflow_id": event.get("workflow_id", ""),
                "event_type": event.get("event", ""),
            },
        ) as span:
            message_id = await self.client.xadd(stream, {"data": json.dumps(event)})
            try:
                span.set_attribute("redis.message_id", str(message_id))
            except Exception:
                pass
            return message_id

    async def publish_dead_letter(
        self,
        original_stream: str,
        event: dict,
        failure_reason: str = "",
        retry_after_seconds: float = 0.0,
    ) -> str:
        """Publish a failed event to the dead-letter stream."""
        message_id = await self.publish_event(
            DEAD_LETTER_STREAM,
            build_dead_letter_event(original_stream, event, failure_reason, retry_after_seconds),
        )
        try:
            from shared.sdk.observability.metrics import DEADLETTER_TOTAL

            DEADLETTER_TOTAL.labels(original_stream=original_stream).inc()
        except Exception:
            pass  # metrics are best-effort
        return message_id

    async def consume_events(
        self,
        stream: str,
        group: str,
        consumer: str,
        count: int = 10,
        block_ms: int = 5000,
    ) -> list:
        await self.ensure_group(stream, group)
        with start_span(
            "redis.consume",
            **{
                "redis.stream": stream,
                "redis.group": group,
                "redis.consumer": consumer,
                "redis.operation": "xreadgroup",
            },
        ) as span:
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
            try:
                span.set_attribute("redis.batch_size", len(events))
            except Exception:
                pass
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
        with start_span(
            "redis.consume_multi",
            **{
                "redis.streams": ",".join(streams),
                "redis.group": group,
                "redis.consumer": consumer,
                "redis.operation": "xreadgroup",
            },
        ) as span:
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
            try:
                span.set_attribute("redis.batch_size", len(events))
            except Exception:
                pass
            return events

    async def ack_event(self, stream: str, group: str, message_id: str) -> int:
        with start_span(
            "redis.ack",
            **{
                "redis.stream": stream,
                "redis.group": group,
                "redis.message_id": message_id,
                "redis.operation": "xack",
            },
        ):
            return await self.client.xack(stream, group, message_id)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
