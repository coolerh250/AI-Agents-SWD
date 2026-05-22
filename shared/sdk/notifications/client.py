import contextlib
import json
from datetime import datetime, timezone

from shared.sdk.event_bus.redis_streams import RedisStreamEventBus

NOTIFICATIONS_STREAM = "stream.notifications"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class NotificationClient:
    """Publishes and reads notifications on the stream.notifications Redis stream.

    This is the foundation for future Slack / Discord / Telegram integrations;
    it performs no real external calls — it only writes to a Redis stream.
    """

    STREAM = NOTIFICATIONS_STREAM

    def __init__(self, event_bus: RedisStreamEventBus | None = None) -> None:
        self.event_bus = event_bus or RedisStreamEventBus()

    def build_notification(self, task_id: str, event_type: str, message: str) -> dict:
        return {
            "task_id": task_id,
            "event_type": event_type,
            "message": message,
            "created_at": _utcnow_iso(),
        }

    async def publish_notification(self, task_id: str, event_type: str, message: str) -> dict:
        notification = self.build_notification(task_id, event_type, message)
        entry_id = await self.event_bus.publish_event(self.STREAM, notification)
        return {"id": entry_id, "notification": notification}

    async def list_notifications(self, count: int = 20) -> list[dict]:
        entries = await self.event_bus.client.xrevrange(self.STREAM, "+", "-", count=count)
        notifications: list[dict] = []
        for entry_id, fields in entries:
            raw = fields.get("data", "{}")
            try:
                payload = json.loads(raw)
            except (ValueError, TypeError):
                payload = {"raw": raw}
            notifications.append({"id": entry_id, "notification": payload})
        return notifications

    async def close(self) -> None:
        await self.event_bus.close()


async def send_notification(task_id: str, event_type: str, message: str) -> None:
    """Best-effort fire-and-forget notification; failures are swallowed."""
    client = NotificationClient()
    try:
        await client.publish_notification(task_id, event_type, message)
    except Exception:
        pass
    finally:
        with contextlib.suppress(Exception):
            await client.close()
