import asyncio
import json
import time
import uuid

import httpx
import pytest

from shared.sdk.event_bus.redis_streams import RedisStreamEventBus


def _stack_with_scheduler_up() -> bool:
    # Need the agent pipeline AND the retry-scheduler reachable.
    for port in (8010, 8011, 8012, 8013, 8014, 8015):
        try:
            if httpx.get(f"http://localhost:{port}/health", timeout=3).status_code != 200:
                return False
        except Exception:
            return False
    return True


requires_pipeline_and_scheduler = pytest.mark.skipif(
    not _stack_with_scheduler_up(),
    reason="agent pipeline (8010-8014) + retry-scheduler (8015) not reachable on localhost",
)


async def _wait_for_match(
    bus: RedisStreamEventBus, stream: str, task_id: str, timeout: int = 60
) -> list[dict]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        entries = await bus.client.xrevrange(stream, "+", "-", count=500)
        matches: list[dict] = []
        for _entry_id, fields in entries:
            try:
                payload = json.loads(fields.get("data", "{}"))
            except (ValueError, TypeError):
                continue
            if payload.get("task_id") == task_id:
                matches.append(payload)
        if matches:
            return matches
        await asyncio.sleep(2)
    return []


@requires_pipeline_and_scheduler
async def test_development_agent_simulated_failure_reaches_dead_letter():
    bus = RedisStreamEventBus()
    task_id = f"test-fail-{uuid.uuid4().hex[:8]}"
    workflow_id = f"wf-fail-{uuid.uuid4().hex[:8]}"
    try:
        await bus.publish_event(
            "stream.tasks",
            {
                "event": "task.created",
                "task_id": task_id,
                "workflow_id": workflow_id,
                "source": "test",
                "request": {"type": "dev.test", "simulate_failure": True},
            },
        )
        dl_matches = await _wait_for_match(bus, "stream.deadletter", task_id, timeout=45)
    finally:
        await bus.close()
    assert dl_matches, "development-agent's controlled failure did not reach stream.deadletter"
    # the dead-letter event carries the failure metadata the spec requires
    first = dl_matches[0]
    assert first["event"] == "deadletter"
    assert first["original_stream"] == "stream.development"
    assert first["retry_count"] >= 3
    assert first["max_retries"] == 3
    assert "failure_reason" in first
    assert "failed_at" in first


@requires_pipeline_and_scheduler
async def test_simulated_failure_eventually_reaches_terminal_failure():
    bus = RedisStreamEventBus()
    task_id = f"test-term-{uuid.uuid4().hex[:8]}"
    workflow_id = f"wf-term-{uuid.uuid4().hex[:8]}"
    try:
        await bus.publish_event(
            "stream.tasks",
            {
                "event": "task.created",
                "task_id": task_id,
                "workflow_id": workflow_id,
                "source": "test",
                "request": {"type": "dev.test", "simulate_failure": True},
            },
        )
        terminal_matches = await _wait_for_match(
            bus, "stream.deadletter.terminal", task_id, timeout=90
        )
    finally:
        await bus.close()
    assert terminal_matches, "task did not reach terminal_failure after retries were exhausted"
    terminal = terminal_matches[0]
    assert terminal["event"] == "retry.terminal_failure"
    assert terminal["terminal_failure"] is True
    assert terminal["retry_count"] > terminal["max_retries"]


@requires_pipeline_and_scheduler
async def test_retry_scheduler_progresses_retry_count():
    bus = RedisStreamEventBus()
    task_id = f"test-progress-{uuid.uuid4().hex[:8]}"
    workflow_id = f"wf-progress-{uuid.uuid4().hex[:8]}"
    try:
        await bus.publish_event(
            "stream.tasks",
            {
                "event": "task.created",
                "task_id": task_id,
                "workflow_id": workflow_id,
                "source": "test",
                "request": {"type": "dev.test", "simulate_failure": True},
            },
        )
        # wait until retries have been exhausted at least twice so the scheduler
        # has had a chance to requeue and a terminal_failure has been emitted.
        await _wait_for_match(bus, "stream.deadletter.terminal", task_id, timeout=90)
        dl_matches = await _wait_for_match(bus, "stream.deadletter", task_id, timeout=10)
    finally:
        await bus.close()
    assert len(dl_matches) >= 1
    counts = sorted({m.get("retry_count") for m in dl_matches if m.get("retry_count") is not None})
    # retry_count progression: a DLQ entry at >=3 (in-stream exhaustion), and a
    # later entry at >max_retries once the scheduler has requeued once.
    assert max(counts) >= 3
