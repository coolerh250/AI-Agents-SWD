import time
import uuid

import httpx
import pytest

from resume_engine import ResumeEngine
from workflow import run_mock_workflow

ORCHESTRATOR = "http://localhost:8000"
APPROVAL_ENGINE = "http://localhost:8002"


def _services_up() -> bool:
    for port in (8000, 8001, 8002, 8003):
        try:
            if httpx.get(f"http://localhost:{port}/health", timeout=3).status_code != 200:
                return False
        except Exception:
            return False
    return True


pytestmark = pytest.mark.skipif(
    not _services_up(),
    reason="orchestrator + governance services not reachable on localhost",
)


def _task_id(kind: str) -> str:
    return f"test-resumeflow-{kind}-{uuid.uuid4().hex[:8]}"


async def _start_production_workflow(task_id: str) -> dict:
    result = await run_mock_workflow(
        {"task_id": task_id, "source": "test", "request": {"type": "production.deploy"}}
    )
    assert result["stage"] == "waiting_approval"
    assert result["approval_required"] is True
    return result


def _approve(request_id: str) -> None:
    response = httpx.post(
        f"{APPROVAL_ENGINE}/approval/approve",
        json={"request_id": request_id, "decided_by": "pytest"},
        timeout=5,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approved"


def _poll_stage(task_id: str, expected: str, timeout: int = 30) -> dict | None:
    deadline = time.time() + timeout
    last: dict | None = None
    while time.time() < deadline:
        response = httpx.get(f"{ORCHESTRATOR}/workflow/{task_id}", timeout=5)
        if response.status_code == 200:
            last = response.json()
            if last.get("stage") == expected:
                return last
        time.sleep(2)
    return last


async def test_on_approval_event_approved_resumes_workflow():
    task_id = _task_id("approved")
    await _start_production_workflow(task_id)
    resumed = await ResumeEngine().on_approval_event(task_id, "approved")
    assert resumed is not None
    assert resumed["stage"] == "completed"
    assert resumed["execution_result"]["production_executed"] is False
    assert resumed["execution_result"]["resumed"] is True


async def test_on_approval_event_rejected_marks_workflow_rejected():
    task_id = _task_id("rejected")
    await _start_production_workflow(task_id)
    rejected = await ResumeEngine().on_approval_event(task_id, "rejected")
    assert rejected is not None
    assert rejected["stage"] == "rejected"
    assert rejected["execution_result"]["production_executed"] is False


async def test_resume_api_rejects_unapproved_workflow():
    task_id = _task_id("unapproved")
    await _start_production_workflow(task_id)
    response = httpx.post(f"{ORCHESTRATOR}/workflow/resume/{task_id}", timeout=10)
    assert response.status_code == 409


async def test_resume_api_resumes_after_approval():
    task_id = _task_id("api")
    result = await _start_production_workflow(task_id)
    _approve(result["approval_request_id"])
    response = httpx.post(f"{ORCHESTRATOR}/workflow/resume/{task_id}", timeout=10)
    assert response.status_code == 200
    body = response.json()
    assert body["stage"] == "completed"
    assert body["execution_result"]["production_executed"] is False


async def test_redis_listener_resumes_workflow_after_approval():
    task_id = _task_id("listener")
    result = await _start_production_workflow(task_id)
    # Approving publishes approval.approved to stream.approvals; the orchestrator
    # consumer-group listener should pick it up and resume the workflow.
    _approve(result["approval_request_id"])
    final = _poll_stage(task_id, "completed", timeout=30)
    assert final is not None, "workflow was not resumed by the listener in time"
    assert final["stage"] == "completed"
    assert final["execution_result"]["production_executed"] is False
