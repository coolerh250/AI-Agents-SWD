import uuid

import pytest

from shared.sdk.workflow_store.store import WorkflowStore

_DB_SKIP = "no reachable PostgreSQL; skipping workflow store test"


async def _store_or_skip() -> WorkflowStore:
    store = WorkflowStore()
    try:
        await store.get_workflow_state("__connectivity_probe__")
    except Exception:
        pytest.skip(_DB_SKIP)
    return store


def _task_id() -> str:
    return f"test-store-{uuid.uuid4().hex[:8]}"


async def test_create_and_get_workflow_state():
    store = await _store_or_skip()
    task_id = _task_id()
    created = await store.create_workflow_state(task_id, {"type": "dev.test"}, stage="intake")
    assert created["task_id"] == task_id
    assert created["stage"] == "intake"

    fetched = await store.get_workflow_state(task_id)
    assert fetched is not None
    assert fetched["task_id"] == task_id
    assert fetched["request"] == {"type": "dev.test"}


async def test_update_workflow_state():
    store = await _store_or_skip()
    task_id = _task_id()
    await store.create_workflow_state(task_id, {"type": "production.deploy"})
    updated = await store.update_workflow_state(
        task_id,
        stage="waiting_approval",
        state={"task_id": task_id, "stage": "waiting_approval"},
        approval_required=True,
        approval_status="pending",
        risk_level="high",
        execution_result={"status": "blocked_pending_approval"},
    )
    assert updated is not None
    assert updated["stage"] == "waiting_approval"
    assert updated["approval_required"] is True
    assert updated["approval_status"] == "pending"
    assert updated["risk_level"] == "high"


async def test_get_unknown_workflow_returns_none():
    store = await _store_or_skip()
    assert await store.get_workflow_state(_task_id()) is None


async def test_list_workflows_and_filter():
    store = await _store_or_skip()
    task_id = _task_id()
    await store.create_workflow_state(task_id, {"type": "dev.test"})
    await store.update_workflow_state(
        task_id,
        stage="waiting_approval",
        state={"task_id": task_id},
        approval_required=True,
        approval_status="pending",
        risk_level="high",
        execution_result={},
    )
    all_workflows = await store.list_workflows()
    assert any(w["task_id"] == task_id for w in all_workflows)

    waiting = await store.list_workflows(status="waiting_approval")
    assert any(w["task_id"] == task_id for w in waiting)


async def test_append_artifact_and_audit_ref():
    store = await _store_or_skip()
    task_id = _task_id()
    await store.create_workflow_state(task_id, {"type": "dev.test"})

    after_artifact = await store.append_artifact(task_id, {"type": "spec", "name": "demo"})
    assert after_artifact is not None
    assert {"type": "spec", "name": "demo"} in after_artifact["state"]["artifacts"]

    after_ref = await store.append_audit_ref(task_id, "audit-123")
    assert after_ref is not None
    assert "audit-123" in after_ref["state"]["audit_refs"]
