import json
import os

import redis.asyncio as aioredis
from redis.exceptions import ResponseError

DEFAULT_REDIS_URL = "redis://localhost:6379"


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

    async def ack_event(self, stream: str, group: str, message_id: str) -> int:
        return await self.client.xack(stream, group, message_id)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
