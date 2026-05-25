import uuid

import pytest
from fastapi import HTTPException

from main import workflow_progress, workflow_timeline
from progress import build_agent_timeline, build_retry_timeline
from shared.sdk.workflow_store.store import WorkflowStore


def test_build_agent_timeline_orders_by_started_at():
    executions = [
        {
            "agent": "qa-agent",
            "status": "completed",
            "started_at": "2026-05-25T01:00:02",
            "completed_at": "2026-05-25T01:00:03",
        },
        {
            "agent": "intake-agent",
            "status": "completed",
            "started_at": "2026-05-25T01:00:00",
            "completed_at": "2026-05-25T01:00:00.5",
        },
        {
            "agent": "devops-agent",
            "status": "completed",
            "started_at": "2026-05-25T01:00:03",
            "completed_at": "2026-05-25T01:00:04",
        },
    ]
    timeline = build_agent_timeline(executions)
    assert [e["phase"] for e in timeline] == ["intake-agent", "qa-agent", "devops-agent"]
    for entry in timeline:
        assert entry["duration_ms"] is not None
        assert entry["duration_ms"] >= 0


def test_build_agent_timeline_handles_missing_timestamps():
    executions = [{"agent": "a", "status": "started", "started_at": None, "completed_at": None}]
    timeline = build_agent_timeline(executions)
    assert timeline[0]["phase"] == "a"
    assert timeline[0]["duration_ms"] is None


def test_build_retry_timeline_extracts_dlq_metadata():
    raw = [
        {
            "id": "1-0",
            "payload": {
                "original_stream": "stream.development",
                "retry_count": 3,
                "max_retries": 3,
                "failure_reason": "boom",
                "failed_at": "2026-05-25T01:00:05",
            },
        },
        {
            "id": "2-0",
            "payload": {
                "original_stream": "stream.development",
                "retry_count": 4,
                "max_retries": 3,
                "failure_reason": "boom",
                "failed_at": "2026-05-25T01:00:07",
            },
        },
    ]
    timeline = build_retry_timeline(raw)
    assert [e["retry_count"] for e in timeline] == [3, 4]
    assert all(e["original_stream"] == "stream.development" for e in timeline)


def test_build_retry_timeline_skips_invalid_entries():
    raw = [{"id": "bad"}, {"payload": "not a dict"}, {"payload": {"original_stream": "s"}}]
    timeline = build_retry_timeline(raw)
    assert len(timeline) == 1


async def _store_or_skip() -> WorkflowStore:
    store = WorkflowStore()
    try:
        await store.get_workflow_state("__timeline_probe__")
    except Exception:
        pytest.skip("no reachable PostgreSQL; skipping timeline API test")
    return store


async def _seed_dispatched_workflow(
    store: WorkflowStore, task_id: str, trace_id: str, workflow_id: str
) -> None:
    await store.create_workflow_state(task_id, {"type": "dev.test"}, stage="dispatched")
    await store.update_workflow_state(
        task_id,
        stage="dispatched",
        state={
            "task_id": task_id,
            "workflow_id": workflow_id,
            "trace_id": trace_id,
            "stage": "dispatched",
            "audit_refs": [],
        },
        approval_required=False,
        approval_status="not_required",
        risk_level="low",
        execution_result={"status": "awaiting_agents", "dispatched": True},
    )


async def test_workflow_progress_returns_traces_and_timelines():
    store = await _store_or_skip()
    task_id = f"test-tl-{uuid.uuid4().hex[:8]}"
    trace_id = "a" * 32
    await _seed_dispatched_workflow(store, task_id, trace_id=trace_id, workflow_id="wf-tl-1")
    result = await workflow_progress(task_id)
    assert result["traces"]["trace_id"] == trace_id
    assert result["traces"]["workflow_id"] == "wf-tl-1"
    assert isinstance(result["agent_timeline"], list)
    assert isinstance(result["retry_timeline"], list)


async def test_workflow_timeline_endpoint_returns_chronological_view():
    store = await _store_or_skip()
    task_id = f"test-tl-ep-{uuid.uuid4().hex[:8]}"
    trace_id = "b" * 32
    await _seed_dispatched_workflow(store, task_id, trace_id=trace_id, workflow_id="wf-tl-2")
    result = await workflow_timeline(task_id)
    assert result["task_id"] == task_id
    assert result["traces"]["trace_id"] == trace_id
    for required in (
        "current_stage",
        "execution_status",
        "approval_status",
        "agent_timeline",
        "retry_timeline",
        "timestamps",
    ):
        assert required in result


async def test_workflow_timeline_unknown_returns_404():
    await _store_or_skip()
    with pytest.raises(HTTPException) as exc:
        await workflow_timeline(f"unknown-{uuid.uuid4().hex[:8]}")
    assert exc.value.status_code == 404
