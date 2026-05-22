import asyncio
import json
import time
import uuid

import httpx
import pytest

from shared.sdk.agent_execution.store import AgentExecutionStore
from shared.sdk.event_bus.redis_streams import RedisStreamEventBus

PIPELINE_AGENTS = {
    "intake-agent",
    "requirement-agent",
    "development-agent",
    "qa-agent",
    "devops-agent",
}


def _pipeline_up() -> bool:
    for port in (8010, 8011, 8012, 8013, 8014):
        try:
            if httpx.get(f"http://localhost:{port}/health", timeout=3).status_code != 200:
                return False
        except Exception:
            return False
    return True


pytestmark = pytest.mark.skipif(
    not _pipeline_up(), reason="full agent pipeline (8010-8014) not reachable on localhost"
)


async def _publish_task(bus: RedisStreamEventBus, task_id: str) -> None:
    await bus.publish_event(
        "stream.tasks",
        {
            "event": "task.created",
            "task_id": task_id,
            "source": "test",
            "request": {"type": "dev.test", "description": "full agent pipeline"},
        },
    )


async def _matches_in_stream(
    bus: RedisStreamEventBus, stream: str, task_id: str, timeout: int = 45
) -> list[dict]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        entries = await bus.client.xrevrange(stream, "+", "-", count=500)
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


async def _wait_for_executions(
    store: AgentExecutionStore, task_id: str, timeout: int = 25
) -> list[dict]:
    deadline = time.time() + timeout
    executions: list[dict] = []
    while time.time() < deadline:
        executions = await store.list_executions(task_id=task_id, status="completed")
        if PIPELINE_AGENTS <= {execution["agent"] for execution in executions}:
            return executions
        await asyncio.sleep(2)
    return executions


async def test_full_pipeline_reaches_deployments():
    bus = RedisStreamEventBus()
    task_id = f"test-pipeline-{uuid.uuid4().hex[:8]}"
    try:
        await _publish_task(bus, task_id)
        qa = await _matches_in_stream(bus, "stream.qa", task_id)
        deployments = await _matches_in_stream(bus, "stream.deployments", task_id)
    finally:
        await bus.close()
    assert qa, "development-agent did not publish to stream.qa"
    assert qa[0]["event"] == "development.completed"
    assert deployments, "qa-agent did not publish to stream.deployments"
    assert deployments[0]["event"] == "qa.completed"


async def test_pipeline_records_completed_executions_for_every_agent():
    bus = RedisStreamEventBus()
    store = AgentExecutionStore()
    task_id = f"test-pipeline-exec-{uuid.uuid4().hex[:8]}"
    try:
        await _publish_task(bus, task_id)
        await _matches_in_stream(bus, "stream.deployments", task_id)
    finally:
        await bus.close()
    executions = await _wait_for_executions(store, task_id)
    completed_agents = {execution["agent"] for execution in executions}
    assert PIPELINE_AGENTS <= completed_agents


async def test_devops_execution_is_mock_safe():
    bus = RedisStreamEventBus()
    store = AgentExecutionStore()
    task_id = f"test-pipeline-devops-{uuid.uuid4().hex[:8]}"
    try:
        await _publish_task(bus, task_id)
        await _matches_in_stream(bus, "stream.deployments", task_id)
    finally:
        await bus.close()
    deadline = time.time() + 25
    devops_execution = None
    while time.time() < deadline:
        executions = await store.list_executions(task_id=task_id, agent="devops-agent")
        completed = [e for e in executions if e["status"] == "completed"]
        if completed:
            devops_execution = completed[0]
            break
        await asyncio.sleep(2)
    assert devops_execution is not None, "devops-agent did not complete"
    metadata = devops_execution["metadata"]
    assert metadata.get("environment") == "test"
    assert metadata.get("production_executed") is False
    assert metadata.get("mock") is True
