import uuid

import pytest
from fastapi import HTTPException

from main import abort_workflow
from shared.sdk.workflow_store.store import WorkflowStore
from workflow_events import WorkflowEventConsumer


async def _store_or_skip() -> WorkflowStore:
    store = WorkflowStore()
    try:
        await store.get_workflow_state("__abort_probe__")
    except Exception:
        pytest.skip("no reachable PostgreSQL; skipping workflow abort test")
    return store


async def _seed_dispatched(store: WorkflowStore, task_id: str) -> None:
    await store.create_workflow_state(task_id, {"type": "dev.test"}, stage="dispatched")
    await store.update_workflow_state(
        task_id,
        stage="dispatched",
        state={
            "task_id": task_id,
            "workflow_id": f"wf-{uuid.uuid4().hex[:8]}",
            "stage": "dispatched",
            "audit_refs": [],
        },
        approval_required=False,
        approval_status="not_required",
        risk_level="low",
        execution_result={"status": "awaiting_agents", "dispatched": True},
    )


async def _seed_aborted(store: WorkflowStore, task_id: str) -> None:
    await store.create_workflow_state(task_id, {"type": "dev.test"}, stage="aborted")
    await store.update_workflow_state(
        task_id,
        stage="aborted",
        state={
            "task_id": task_id,
            "workflow_id": "wf-already-aborted",
            "stage": "aborted",
            "aborted_at": "2026-05-25T00:00:00+00:00",
            "abort_reason": "test seed",
            "audit_refs": [],
        },
        approval_required=False,
        approval_status="not_required",
        risk_level="low",
        execution_result={"status": "aborted"},
    )


async def test_abort_dispatched_workflow_marks_aborted():
    store = await _store_or_skip()
    task_id = f"test-abort-{uuid.uuid4().hex[:8]}"
    await _seed_dispatched(store, task_id)
    result = await abort_workflow(task_id, {"reason": "operator abort"})
    assert result["stage"] == "aborted"
    assert result["execution_result"]["status"] == "aborted"
    assert result["execution_result"]["abort_reason"] == "operator abort"
    persisted = await store.get_workflow_state(task_id)
    assert persisted is not None
    assert persisted["stage"] == "aborted"
    assert persisted["state"]["abort_reason"] == "operator abort"
    assert persisted["state"]["aborted_at"]
    assert persisted["execution_result"]["production_executed"] is False


async def test_abort_unknown_workflow_returns_404():
    await _store_or_skip()
    with pytest.raises(HTTPException) as exc:
        await abort_workflow(f"unknown-{uuid.uuid4().hex[:8]}")
    assert exc.value.status_code == 404


async def test_workflow_event_consumer_ignores_events_for_aborted_workflow():
    store = await _store_or_skip()
    task_id = f"test-abort-ignore-{uuid.uuid4().hex[:8]}"
    await _seed_aborted(store, task_id)
    consumer = WorkflowEventConsumer(store=store)
    result = await consumer.handle_event({"event": "development.completed", "task_id": task_id})
    assert result is None  # ignored
    persisted = await store.get_workflow_state(task_id)
    assert persisted is not None
    assert persisted["stage"] == "aborted"  # not advanced by the ignored event
    assert persisted["execution_result"]["status"] == "aborted"


async def test_workflow_event_consumer_ignores_events_for_canceled_workflow():
    store = await _store_or_skip()
    task_id = f"test-cancel-ignore-{uuid.uuid4().hex[:8]}"
    await store.create_workflow_state(task_id, {"type": "dev.test"}, stage="canceled")
    await store.update_workflow_state(
        task_id,
        stage="canceled",
        state={"task_id": task_id, "stage": "canceled", "audit_refs": []},
        approval_required=False,
        approval_status="not_required",
        risk_level="low",
        execution_result={"status": "canceled"},
    )
    consumer = WorkflowEventConsumer(store=store)
    result = await consumer.handle_event({"event": "qa.completed", "task_id": task_id})
    assert result is None
    persisted = await store.get_workflow_state(task_id)
    assert persisted is not None
    assert persisted["stage"] == "canceled"
