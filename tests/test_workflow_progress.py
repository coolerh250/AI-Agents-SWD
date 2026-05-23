import uuid

import pytest
from fastapi import HTTPException

from main import workflow_progress
from progress import PIPELINE_AGENTS, build_progress
from shared.sdk.agent_execution.store import AgentExecutionStore
from shared.sdk.workflow_store.store import WorkflowStore


def _workflow(stage: str, approval_status: str = "not_required", state: dict | None = None) -> dict:
    return {
        "task_id": "wf-1",
        "stage": stage,
        "approval_required": False,
        "approval_status": approval_status,
        "risk_level": "low",
        "request": {},
        "state": state or {"workflow_id": "wf-test-1"},
        "execution_result": {},
        "created_at": "2026-05-22T00:00:00+00:00",
        "updated_at": "2026-05-22T00:00:00+00:00",
    }


def _execution(agent: str, status: str) -> dict:
    return {"agent": agent, "status": status, "started_at": "t0", "completed_at": "t1"}


def test_build_progress_dispatched_has_all_agents_pending():
    progress = build_progress(_workflow("dispatched"), [])
    assert progress["execution_status"] == "dispatched"
    assert progress["current_stage"] == "dispatched"
    assert progress["completed_agents"] == []
    assert progress["pending_agents"] == PIPELINE_AGENTS
    assert progress["workflow_id"] == "wf-test-1"


def test_build_progress_in_progress_when_some_agents_done():
    executions = [
        _execution("intake-agent", "completed"),
        _execution("requirement-agent", "completed"),
    ]
    progress = build_progress(_workflow("in_progress"), executions)
    assert progress["execution_status"] == "in_progress"
    assert progress["completed_agents"] == ["intake-agent", "requirement-agent"]
    assert "devops-agent" in progress["pending_agents"]


def test_build_progress_completed_when_all_agents_done():
    executions = [_execution(agent, "completed") for agent in PIPELINE_AGENTS]
    progress = build_progress(_workflow("completed"), executions)
    assert progress["execution_status"] == "completed"
    assert progress["completed_agents"] == PIPELINE_AGENTS
    assert progress["pending_agents"] == []


def test_build_progress_waiting_approval():
    progress = build_progress(_workflow("waiting_approval", approval_status="pending"), [])
    assert progress["execution_status"] == "waiting_approval"
    assert progress["approval_status"] == "pending"


def test_build_progress_failed_when_an_agent_fails():
    executions = [
        _execution("intake-agent", "completed"),
        _execution("requirement-agent", "failed"),
    ]
    progress = build_progress(_workflow("in_progress"), executions)
    assert progress["execution_status"] == "failed"
    assert "requirement-agent" in progress["failed_agents"]


def test_build_progress_has_all_required_fields():
    progress = build_progress(_workflow("dispatched"), [])
    for field in (
        "current_stage",
        "completed_agents",
        "pending_agents",
        "execution_status",
        "approval_status",
        "timestamps",
    ):
        assert field in progress


async def _db_or_skip() -> WorkflowStore:
    store = WorkflowStore()
    try:
        await store.get_workflow_state("__progress_probe__")
    except Exception:
        pytest.skip("no reachable PostgreSQL; skipping progress API test")
    return store


async def test_progress_endpoint_returns_progress_for_persisted_workflow():
    store = await _db_or_skip()
    task_id = f"test-progress-{uuid.uuid4().hex[:8]}"
    await store.create_workflow_state(task_id, {"type": "dev.test"}, stage="dispatched")
    await store.update_workflow_state(
        task_id,
        stage="dispatched",
        state={"task_id": task_id, "workflow_id": "wf-progress", "stage": "dispatched"},
        approval_required=False,
        approval_status="not_required",
        risk_level="low",
        execution_result={"status": "awaiting_agents"},
    )
    await AgentExecutionStore().create_execution(task_id, "intake-agent")
    result = await workflow_progress(task_id)
    assert result["task_id"] == task_id
    assert result["current_stage"] == "dispatched"
    assert result["execution_status"] == "dispatched"
    assert result["workflow_id"] == "wf-progress"
    assert "intake-agent" in result["pending_agents"]


async def test_progress_endpoint_unknown_workflow_raises_404():
    await _db_or_skip()
    with pytest.raises(HTTPException) as exc:
        await workflow_progress(f"unknown-{uuid.uuid4().hex[:8]}")
    assert exc.value.status_code == 404
