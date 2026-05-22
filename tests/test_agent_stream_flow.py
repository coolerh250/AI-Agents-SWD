import asyncio
import json
import time
import uuid

import httpx
import pytest

from shared.sdk.event_bus.redis_streams import RedisStreamEventBus


def _agents_up() -> bool:
    for port in (8010, 8011):
        try:
            if httpx.get(f"http://localhost:{port}/health", timeout=3).status_code != 200:
                return False
        except Exception:
            return False
    return True


pytestmark = pytest.mark.skipif(
    not _agents_up(), reason="intake-agent / requirement-agent not reachable on localhost"
)


async def _publish_task(bus: RedisStreamEventBus, task_id: str) -> None:
    await bus.publish_event(
        "stream.tasks",
        {
            "event": "task.created",
            "task_id": task_id,
            "source": "test",
            "request": {"type": "dev.test", "description": "agent stream flow"},
        },
    )


async def _matches_in_stream(
    bus: RedisStreamEventBus, stream: str, task_id: str, timeout: int = 30
) -> list[dict]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        entries = await bus.client.xrevrange(stream, "+", "-", count=400)
        matches = []
        for _entry_id, fields in entries:
            try:
                payload = json.loads(fields.get("data", "{}"))
            except (ValueError, TypeError):
                continue
            if payload.get("task_id") == task_id:
                matches.append(payload)
        if matches:
            return matches
        await asyncio.sleep(1)
    return []


async def test_intake_agent_forwards_task_to_requirements():
    bus = RedisStreamEventBus()
    task_id = f"test-flow-intake-{uuid.uuid4().hex[:8]}"
    try:
        await _publish_task(bus, task_id)
        forwarded = await _matches_in_stream(bus, "stream.requirements", task_id)
    finally:
        await bus.close()
    assert forwarded, "intake-agent did not forward the task to stream.requirements"
    assert forwarded[0]["normalized_by"] == "intake-agent"


async def test_requirement_agent_emits_requirement_completed():
    bus = RedisStreamEventBus()
    task_id = f"test-flow-req-{uuid.uuid4().hex[:8]}"
    try:
        await _publish_task(bus, task_id)
        completed = await _matches_in_stream(bus, "stream.development", task_id)
    finally:
        await bus.close()
    assert completed, "requirement-agent did not emit requirement.completed"
    assert completed[0]["event"] == "requirement.completed"
    assert completed[0]["artifact"]["type"] == "requirement_spec"


async def test_agent_flow_writes_audit_and_notifications():
    bus = RedisStreamEventBus()
    task_id = f"test-flow-audit-{uuid.uuid4().hex[:8]}"
    try:
        await _publish_task(bus, task_id)
        await _matches_in_stream(bus, "stream.development", task_id)
        audit = await _matches_in_stream(bus, "stream.audit", task_id, timeout=15)
        notifications = await _matches_in_stream(bus, "stream.notifications", task_id, timeout=15)
    finally:
        await bus.close()
    audit_agents = {entry.get("agent") for entry in audit}
    assert "intake-agent" in audit_agents
    assert "requirement-agent" in audit_agents
    notification_types = {entry.get("event_type") for entry in notifications}
    assert "agent.intake_completed" in notification_types
    assert "requirement.completed" in notification_types
