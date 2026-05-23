import asyncio
import json
import time
import uuid

import httpx
import pytest

from dispatch import TASKS_STREAM
from resume_engine import ResumeEngine
from shared.sdk.event_bus.redis_streams import RedisStreamEventBus
from workflow import run_mock_workflow


def _services_up() -> bool:
    for port in (8001, 8002, 8003):
        try:
            if httpx.get(f"http://localhost:{port}/health", timeout=3).status_code != 200:
                return False
        except Exception:
            return False
    return True


pytestmark = pytest.mark.skipif(
    not _services_up(),
    reason="governance services (policy/approval/audit) not reachable on localhost",
)


async def _bus_or_skip() -> RedisStreamEventBus:
    bus = RedisStreamEventBus()
    try:
        await bus.client.ping()
    except Exception:
        await bus.close()
        pytest.skip("no reachable Redis; skipping dispatch test")
    return bus


async def _find_dispatch_event(
    bus: RedisStreamEventBus, task_id: str, timeout: int = 10
) -> dict | None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        entries = await bus.client.xrevrange(TASKS_STREAM, "+", "-", count=500)
        for _entry_id, fields in entries:
            try:
                payload = json.loads(fields.get("data", "{}"))
            except (ValueError, TypeError):
                continue
            if payload.get("task_id") == task_id:
                return payload
        await asyncio.sleep(0.5)
    return None


async def test_non_production_workflow_dispatches_to_stream_tasks():
    bus = await _bus_or_skip()
    task_id = f"test-dispatch-dev-{uuid.uuid4().hex[:8]}"
    try:
        result = await run_mock_workflow(
            {"task_id": task_id, "source": "test", "request": {"type": "dev.test"}}
        )
        assert result["stage"] == "dispatched"
        assert result["execution_result"]["status"] == "awaiting_agents"
        assert result["execution_result"]["dispatched"] is True
        event = await _find_dispatch_event(bus, task_id)
    finally:
        await bus.close()
    assert event is not None, "orchestrator did not publish task.created to stream.tasks"
    assert event["event"] == "task.created"
    assert event["task_id"] == task_id
    assert event["workflow_id"] == result["workflow_id"]
    assert event["workflow_id"]


async def test_production_deploy_is_not_dispatched_without_approval():
    bus = await _bus_or_skip()
    task_id = f"test-dispatch-prod-{uuid.uuid4().hex[:8]}"
    try:
        result = await run_mock_workflow(
            {"task_id": task_id, "source": "test", "request": {"type": "production.deploy"}}
        )
        assert result["stage"] == "waiting_approval"
        assert result["approval_required"] is True
        assert result["execution_result"]["dispatched"] is False
        event = await _find_dispatch_event(bus, task_id, timeout=5)
    finally:
        await bus.close()
    assert event is None, "production.deploy was dispatched to stream.tasks before approval"


async def test_approved_production_deploy_is_dispatched():
    bus = await _bus_or_skip()
    task_id = f"test-dispatch-approved-{uuid.uuid4().hex[:8]}"
    try:
        result = await run_mock_workflow(
            {"task_id": task_id, "source": "test", "request": {"type": "production.deploy"}}
        )
        assert result["stage"] == "waiting_approval"
        resumed = await ResumeEngine().on_approval_event(task_id, "approved")
        assert resumed is not None
        assert resumed["stage"] == "dispatched"
        assert resumed["execution_result"]["production_executed"] is False
        event = await _find_dispatch_event(bus, task_id)
    finally:
        await bus.close()
    assert event is not None, "approved production.deploy was not dispatched to stream.tasks"
    assert event["task_id"] == task_id
