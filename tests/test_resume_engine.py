import uuid

import pytest

from resume_engine import ResumeEngine, ResumeError
from shared.sdk.workflow_store.store import WorkflowStore

_DB_SKIP = "no reachable PostgreSQL; skipping resume engine test"


async def _store_or_skip() -> WorkflowStore:
    store = WorkflowStore()
    try:
        await store.get_workflow_state("__connectivity_probe__")
    except Exception:
        pytest.skip(_DB_SKIP)
    return store


def _task_id() -> str:
    return f"test-resume-{uuid.uuid4().hex[:8]}"


async def _seed(store: WorkflowStore, task_id: str, approval_status: str) -> None:
    await store.create_workflow_state(task_id, {"type": "production.deploy"})
    await store.update_workflow_state(
        task_id,
        stage="waiting_approval",
        state={"task_id": task_id, "stage": "waiting_approval", "audit_refs": []},
        approval_required=True,
        approval_status=approval_status,
        risk_level="high",
        execution_result={"status": "blocked_pending_approval"},
    )


async def test_replay_returns_persisted_state():
    store = await _store_or_skip()
    task_id = _task_id()
    await _seed(store, task_id, "pending")
    replay = await ResumeEngine(store).replay_workflow_state(task_id)
    assert replay is not None
    assert replay["task_id"] == task_id
    assert replay["stage"] == "waiting_approval"


async def test_resume_unapproved_workflow_raises():
    store = await _store_or_skip()
    task_id = _task_id()
    await _seed(store, task_id, "pending")
    with pytest.raises(ResumeError):
        await ResumeEngine(store).resume_workflow(task_id)


async def test_resume_unknown_workflow_raises():
    store = await _store_or_skip()
    with pytest.raises(ResumeError):
        await ResumeEngine(store).resume_workflow(_task_id())


async def test_resume_approved_workflow_completes():
    store = await _store_or_skip()
    task_id = _task_id()
    await _seed(store, task_id, "approved")
    resumed = await ResumeEngine(store).resume_workflow(task_id)
    assert resumed is not None
    assert resumed["stage"] == "completed"
    assert resumed["approval_status"] == "approved"
    assert resumed["execution_result"]["production_executed"] is False
    assert resumed["execution_result"]["resumed"] is True


async def test_on_approval_event_approved_resumes():
    store = await _store_or_skip()
    task_id = _task_id()
    await _seed(store, task_id, "pending")
    result = await ResumeEngine(store).on_approval_event(task_id, "approved")
    assert result is not None
    assert result["stage"] == "completed"
    assert result["execution_result"]["production_executed"] is False


async def test_on_approval_event_rejected_marks_rejected():
    store = await _store_or_skip()
    task_id = _task_id()
    await _seed(store, task_id, "pending")
    result = await ResumeEngine(store).on_approval_event(task_id, "rejected")
    assert result is not None
    assert result["stage"] == "rejected"
    assert result["approval_status"] == "rejected"
    assert result["execution_result"]["production_executed"] is False
