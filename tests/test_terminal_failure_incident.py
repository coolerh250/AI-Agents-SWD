import asyncio
import json
import time
import uuid

import httpx
import pytest

from scheduler import RetryScheduler
from shared.sdk.event_bus.redis_streams import RedisStreamEventBus
from shared.sdk.incidents import IncidentStore
from shared.sdk.workflow_store.store import WorkflowStore


def _redis_up() -> bool:
    bus = RedisStreamEventBus(redis_url="redis://localhost:6379")

    async def ping() -> bool:
        try:
            return bool(await bus.client.ping())
        finally:
            await bus.close()

    try:
        return asyncio.get_event_loop().run_until_complete(ping())
    except Exception:
        return False


def _postgres_up() -> bool:
    store = IncidentStore()

    async def probe() -> bool:
        try:
            await store.list_incidents(limit=1)
            return True
        except Exception:
            return False

    try:
        return asyncio.get_event_loop().run_until_complete(probe())
    except Exception:
        return False


requires_runtime = pytest.mark.skipif(
    not (_redis_up() and _postgres_up()),
    reason="redis (6379) or postgres (incident store) not reachable",
)


def test_terminal_failure_records_incident_event_in_module():
    """Scheduler module must expose the symbols Step 15.4 wires."""
    import scheduler as sched_module

    assert hasattr(sched_module.RetryScheduler, "_on_terminal_failure")
    assert hasattr(sched_module.RetryScheduler, "_mark_workflow_failed")


@requires_runtime
async def test_terminal_failure_creates_incident_and_marks_workflow_failed():
    """A dead-letter event whose retry_count already exceeded max_retries must
    create an incident_records row and flip the matching workflow to failed.
    """
    task_id = f"terminal-incident-{uuid.uuid4().hex[:8]}"
    workflow_id = f"wf-{task_id}"

    # Seed a workflow row in 'dispatched' so the scheduler has something to
    # flip. We do NOT run the whole agent pipeline — we just need the row.
    wf_store = WorkflowStore()
    await wf_store.create_workflow_state(task_id, {"type": "dev.test"}, stage="dispatched")

    bus = RedisStreamEventBus(redis_url="redis://localhost:6379")
    sched = RetryScheduler(event_bus=bus)
    try:
        payload = {
            "event": "deadletter",
            "task_id": task_id,
            "workflow_id": workflow_id,
            "original_stream": "stream.development",
            "failure_reason": "simulated terminal failure (test)",
            "retry_count": 4,  # > max_retries triggers terminal branch
            "max_retries": 3,
            "retry_after_seconds": 0.0,
            "failed_at": "2026-05-26T12:00:00+00:00",
            "original_event": {
                "task_id": task_id,
                "workflow_id": workflow_id,
                "event": "development.failed",
            },
        }
        result = await sched.handle(message_id=f"test-msg-{uuid.uuid4().hex[:8]}", payload=payload)
        assert result["action"] == "terminal_failure"
        assert result.get("incident_id"), "scheduler must surface the incident_id"

        # The incident row must be visible in the incident_records table.
        incidents = await IncidentStore().list_incidents(task_id=task_id)
        assert incidents, "no incident created for terminal failure"
        incident = incidents[0]
        assert incident.severity == "sev2"
        assert incident.source == "retry-scheduler"
        assert "terminal failure" in incident.summary.lower()
        # details must carry the retry-scheduler context for the operator.
        for key in ("original_stream", "retry_count", "max_retries", "failure_reason"):
            assert key in incident.details, key

        # workflow_states must be in stage='failed'.
        updated = await wf_store.get_workflow_state(task_id)
        assert updated is not None
        assert updated["stage"] == "failed"
        assert updated["execution_result"]["status"] == "failed"
        assert updated["execution_result"]["production_executed"] is False
    finally:
        await bus.close()


@requires_runtime
async def test_terminal_failure_with_missing_workflow_still_creates_incident():
    """If no workflow_states row exists for the task_id, the scheduler must
    still create the incident and flag workflow_not_found=true in details.
    """
    task_id = f"terminal-orphan-{uuid.uuid4().hex[:8]}"
    bus = RedisStreamEventBus(redis_url="redis://localhost:6379")
    sched = RetryScheduler(event_bus=bus)
    try:
        payload = {
            "task_id": task_id,
            "workflow_id": f"wf-{task_id}",
            "original_stream": "stream.development",
            "failure_reason": "orphan terminal",
            "retry_count": 5,
            "max_retries": 3,
            "original_event": {"task_id": task_id},
        }
        result = await sched.handle(message_id=f"test-msg-{uuid.uuid4().hex[:8]}", payload=payload)
        assert result["action"] == "terminal_failure"
        assert result.get("incident_id")

        incidents = await IncidentStore().list_incidents(task_id=task_id)
        assert incidents
        assert incidents[0].details.get("workflow_not_found") is True
    finally:
        await bus.close()


@requires_runtime
async def test_terminal_failure_publishes_workflow_failed_notification():
    """The retry-scheduler must publish a workflow.failed notification on the
    notifications stream so dashboards / future Slack / future PagerDuty
    integrations can observe the terminal failure."""
    task_id = f"terminal-notif-{uuid.uuid4().hex[:8]}"
    bus = RedisStreamEventBus(redis_url="redis://localhost:6379")

    # Snapshot the notifications stream tail so we don't read pre-existing rows.
    before_entries = await bus.client.xrevrange("stream.notifications", "+", "-", count=1)
    before_id = before_entries[0][0] if before_entries else "0-0"

    sched = RetryScheduler(event_bus=bus)
    try:
        await sched.handle(
            message_id=f"test-msg-{uuid.uuid4().hex[:8]}",
            payload={
                "task_id": task_id,
                "workflow_id": f"wf-{task_id}",
                "original_stream": "stream.development",
                "failure_reason": "notification smoke",
                "retry_count": 5,
                "max_retries": 3,
                "original_event": {"task_id": task_id},
            },
        )

        # Poll the stream tail until we find the workflow.failed notification.
        deadline = time.time() + 10
        found = False
        while time.time() < deadline and not found:
            entries = await bus.client.xrange("stream.notifications", f"({before_id}", "+")
            for _entry_id, fields in entries:
                try:
                    payload = json.loads(fields.get("data", "{}"))
                except (ValueError, TypeError):
                    continue
                if (
                    payload.get("event_type") == "workflow.failed"
                    and payload.get("task_id") == task_id
                ):
                    found = True
                    break
            if not found:
                await asyncio.sleep(0.5)
        assert found, "no workflow.failed notification observed for terminal failure"
    finally:
        await bus.close()


def _audit_up() -> bool:
    try:
        return httpx.get("http://localhost:8003/health", timeout=3).status_code == 200
    except Exception:
        return False


@requires_runtime
@pytest.mark.skipif(not _audit_up(), reason="audit-service not reachable on localhost:8003")
async def test_terminal_failure_writes_audit_event():
    task_id = f"terminal-audit-{uuid.uuid4().hex[:8]}"
    bus = RedisStreamEventBus(redis_url="redis://localhost:6379")
    sched = RetryScheduler(event_bus=bus)
    try:
        await sched.handle(
            message_id=f"test-msg-{uuid.uuid4().hex[:8]}",
            payload={
                "task_id": task_id,
                "workflow_id": f"wf-{task_id}",
                "original_stream": "stream.development",
                "failure_reason": "audit smoke",
                "retry_count": 5,
                "max_retries": 3,
                "original_event": {"task_id": task_id},
            },
        )
        # Fire-and-forget audit; poll a few times.
        deadline = time.time() + 10
        found = False
        while time.time() < deadline and not found:
            events = httpx.get(f"http://localhost:8003/audit/events/{task_id}", timeout=3).json()
            if any(ev.get("decision_type") == "workflow_failed" for ev in events.get("events", [])):
                found = True
                break
            await asyncio.sleep(0.5)
        assert found, "no audit event decision_type=workflow_failed observed"
    finally:
        await bus.close()
