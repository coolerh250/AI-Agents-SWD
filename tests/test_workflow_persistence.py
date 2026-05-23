import uuid

import httpx
import pytest

from resume_engine import ResumeEngine
from shared.sdk.workflow_store.store import WorkflowStore
from workflow import run_mock_workflow


def _services_up() -> bool:
    for port in (8001, 8002, 8003):
        try:
            if httpx.get(f"http://localhost:{port}/health", timeout=3).status_code != 200:
                return False
        except Exception:
            return False
    return True


pytestmark = pytest.mark.skipif(
    not _services_up(),
    reason="governance services (policy/approval/audit) not reachable on localhost",
)


def _task_id(kind: str) -> str:
    return f"test-persist-{kind}-{uuid.uuid4().hex[:8]}"


async def test_non_production_workflow_is_persisted():
    task_id = _task_id("dev")
    await run_mock_workflow({"task_id": task_id, "source": "test", "request": {"type": "dev.test"}})
    stored = await WorkflowStore().get_workflow_state(task_id)
    assert stored is not None
    assert stored["stage"] == "dispatched"
    assert stored["approval_required"] is False
    assert stored["execution_result"]["production_executed"] is False
    assert stored["state"]["task_id"] == task_id


async def test_waiting_approval_workflow_is_persisted():
    task_id = _task_id("prod")
    await run_mock_workflow(
        {"task_id": task_id, "source": "test", "request": {"type": "production.deploy"}}
    )
    stored = await WorkflowStore().get_workflow_state(task_id)
    assert stored is not None
    assert stored["stage"] == "waiting_approval"
    assert stored["approval_required"] is True
    assert stored["approval_status"] == "pending"
    assert stored["execution_result"]["production_executed"] is False


async def test_persisted_state_carries_full_workflow_state():
    task_id = _task_id("full")
    await run_mock_workflow({"task_id": task_id, "source": "test", "request": {"type": "dev.test"}})
    stored = await WorkflowStore().get_workflow_state(task_id)
    assert stored is not None
    state = stored["state"]
    for field in ("task_id", "stage", "artifacts", "audit_refs", "execution_result"):
        assert field in state
    assert len(state["audit_refs"]) >= 1


async def test_replay_matches_persisted_workflow():
    task_id = _task_id("replay")
    await run_mock_workflow(
        {"task_id": task_id, "source": "test", "request": {"type": "production.deploy"}}
    )
    replay = await ResumeEngine().replay_workflow_state(task_id)
    assert replay is not None
    assert replay["task_id"] == task_id
    assert replay["stage"] == "waiting_approval"
