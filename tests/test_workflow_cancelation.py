import uuid

import pytest
from fastapi import HTTPException

from main import cancel_workflow
from shared.sdk.workflow_store.store import WorkflowStore


async def _store_or_skip() -> WorkflowStore:
    store = WorkflowStore()
    try:
        await store.get_workflow_state("__cancel_probe__")
    except Exception:
        pytest.skip("no reachable PostgreSQL; skipping workflow cancel test")
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


async def _seed_completed(store: WorkflowStore, task_id: str) -> None:
    await store.create_workflow_state(task_id, {"type": "dev.test"}, stage="completed")
    await store.update_workflow_state(
        task_id,
        stage="completed",
        state={"task_id": task_id, "stage": "completed", "audit_refs": []},
        approval_required=False,
        approval_status="not_required",
        risk_level="low",
        execution_result={"status": "completed"},
    )


async def test_cancel_dispatched_workflow_marks_canceled():
    store = await _store_or_skip()
    task_id = f"test-cancel-{uuid.uuid4().hex[:8]}"
    await _seed_dispatched(store, task_id)
    result = await cancel_workflow(task_id, {"reason": "user requested cancel"})
    assert result["stage"] == "canceled"
    assert result["execution_result"]["status"] == "canceled"
    assert result["execution_result"]["cancel_reason"] == "user requested cancel"
    persisted = await store.get_workflow_state(task_id)
    assert persisted is not None
    assert persisted["stage"] == "canceled"
    assert persisted["state"]["cancel_reason"] == "user requested cancel"
    assert persisted["state"]["canceled_at"]
    assert persisted["execution_result"]["production_executed"] is False


async def test_cancel_unknown_workflow_returns_404():
    await _store_or_skip()
    with pytest.raises(HTTPException) as exc:
        await cancel_workflow(f"unknown-{uuid.uuid4().hex[:8]}")
    assert exc.value.status_code == 404


async def test_cancel_completed_workflow_returns_409():
    store = await _store_or_skip()
    task_id = f"test-cancel-done-{uuid.uuid4().hex[:8]}"
    await _seed_completed(store, task_id)
    with pytest.raises(HTTPException) as exc:
        await cancel_workflow(task_id, {"reason": "too late"})
    assert exc.value.status_code == 409


async def test_cancel_persists_default_reason_when_payload_missing():
    store = await _store_or_skip()
    task_id = f"test-cancel-noreason-{uuid.uuid4().hex[:8]}"
    await _seed_dispatched(store, task_id)
    result = await cancel_workflow(task_id)
    assert result["stage"] == "canceled"
    assert result["execution_result"]["cancel_reason"] == ""
