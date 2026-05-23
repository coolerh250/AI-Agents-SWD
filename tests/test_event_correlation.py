import asyncio
import json
import time
import uuid

import httpx
import pytest

from shared.sdk.base_agent.stream_agent import StreamAgent
from shared.sdk.event_bus.redis_streams import RedisStreamEventBus


def test_correlation_ids_extracts_task_and_workflow_id():
    ids = StreamAgent.correlation_ids({"task_id": "t-1", "workflow_id": "wf-1", "extra": "x"})
    assert ids == {"task_id": "t-1", "workflow_id": "wf-1"}


def test_correlation_ids_defaults_when_absent():
    ids = StreamAgent.correlation_ids({})
    assert ids["task_id"] == "unknown"
    assert ids["workflow_id"] == ""


def _pipeline_up() -> bool:
    for port in (8010, 8011, 8012, 8013, 8014):
        try:
            if httpx.get(f"http://localhost:{port}/health", timeout=3).status_code != 200:
                return False
        except Exception:
            return False
    return True


requires_pipeline = pytest.mark.skipif(
    not _pipeline_up(), reason="full agent pipeline (8010-8014) not reachable on localhost"
)


async def _first_match(
    bus: RedisStreamEventBus, stream: str, task_id: str, timeout: int = 45
) -> dict | None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        entries = await bus.client.xrevrange(stream, "+", "-", count=500)
        for _entry_id, fields in entries:
            try:
                payload = json.loads(fields.get("data", "{}"))
            except (ValueError, TypeError):
                continue
            if payload.get("task_id") == task_id:
                return payload
        await asyncio.sleep(1)
    return None


@requires_pipeline
async def test_workflow_id_propagates_through_the_pipeline():
    bus = RedisStreamEventBus()
    task_id = f"test-corr-{uuid.uuid4().hex[:8]}"
    workflow_id = f"wf-corr-{uuid.uuid4().hex[:8]}"
    try:
        await bus.publish_event(
            "stream.tasks",
            {
                "event": "task.created",
                "task_id": task_id,
                "workflow_id": workflow_id,
                "source": "test",
                "request": {"type": "dev.test", "description": "correlation"},
            },
        )
        requirements = await _first_match(bus, "stream.requirements", task_id)
        development = await _first_match(bus, "stream.development", task_id)
        qa = await _first_match(bus, "stream.qa", task_id)
        devops = await _first_match(bus, "stream.devops", task_id)
    finally:
        await bus.close()
    for stage_event in (requirements, development, qa, devops):
        assert stage_event is not None, "an agent did not forward the task"
        assert stage_event["task_id"] == task_id
        assert stage_event["workflow_id"] == workflow_id
    # the devops event carries the deployment record, also correlated.
    assert devops["event"] == "devops.deployment_simulated"
    assert devops["artifact"]["workflow_id"] == workflow_id
