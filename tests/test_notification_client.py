import uuid

import pytest

from shared.sdk.notifications.client import NotificationClient, send_notification

_REDIS_SKIP = "no reachable Redis; skipping notification test"


async def _client_or_skip() -> NotificationClient:
    client = NotificationClient()
    try:
        await client.event_bus.client.ping()
    except Exception:
        await client.close()
        pytest.skip(_REDIS_SKIP)
    return client


def test_build_notification():
    notification = NotificationClient().build_notification("task-1", "test", "hello")
    assert notification["task_id"] == "task-1"
    assert notification["event_type"] == "test"
    assert notification["message"] == "hello"
    assert notification["created_at"]


async def test_publish_and_list_notification():
    client = await _client_or_skip()
    task_id = f"test-notif-{uuid.uuid4().hex[:8]}"
    try:
        published = await client.publish_notification(task_id, "unit.test", "published")
        assert published["id"]
        assert published["notification"]["task_id"] == task_id
        items = await client.list_notifications(count=50)
    finally:
        await client.close()
    matching = [i for i in items if i["notification"].get("task_id") == task_id]
    assert len(matching) >= 1
    assert matching[0]["notification"]["event_type"] == "unit.test"


async def test_send_notification_helper():
    client = await _client_or_skip()
    task_id = f"test-send-{uuid.uuid4().hex[:8]}"
    try:
        await send_notification(task_id, "unit.send", "via helper")
        items = await client.list_notifications(count=50)
    finally:
        await client.close()
    assert any(i["notification"].get("task_id") == task_id for i in items)
