import uuid

import httpx
import pytest

GATEWAY = "http://localhost:8004"


def _stack_up() -> bool:
    for port in (8000, 8001, 8002, 8003, 8004):
        try:
            if httpx.get(f"http://localhost:{port}/health", timeout=3).status_code != 200:
                return False
        except Exception:
            return False
    return True


pytestmark = pytest.mark.skipif(
    not _stack_up(), reason="full stack (orchestrator + governance + gateway) not reachable"
)


def _notifications_for(task_id: str, count: int = 100) -> list[dict]:
    body = httpx.get(f"{GATEWAY}/notifications?count={count}", timeout=10).json()
    return [
        n["notification"]
        for n in body["notifications"]
        if n["notification"].get("task_id") == task_id
    ]


def test_intake_dispatch_publishes_notification():
    task_id = f"test-flow-dev-{uuid.uuid4().hex[:8]}"
    response = httpx.post(
        f"{GATEWAY}/intake/mock",
        json={"task_id": task_id, "request": {"type": "dev.test"}},
        timeout=30,
    )
    assert response.status_code == 200
    assert response.json()["stage"] == "dispatched"
    events = _notifications_for(task_id)
    assert any(e["event_type"] == "workflow.dispatched" for e in events)


def test_intake_production_deploy_publishes_waiting_approval_notification():
    task_id = f"test-flow-prod-{uuid.uuid4().hex[:8]}"
    response = httpx.post(
        f"{GATEWAY}/intake/mock",
        json={"task_id": task_id, "request": {"type": "production.deploy"}},
        timeout=30,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["approval_required"] is True
    assert body["stage"] == "waiting_approval"
    assert body["workflow_result"]["execution_result"]["production_executed"] is False
    events = _notifications_for(task_id)
    assert any(e["event_type"] == "workflow.waiting_approval" for e in events)


def test_notifications_test_endpoint_publishes_to_stream():
    task_id = f"test-flow-notif-{uuid.uuid4().hex[:8]}"
    posted = httpx.post(
        f"{GATEWAY}/notifications/test",
        json={"task_id": task_id, "event_type": "flow.test", "message": "flow"},
        timeout=10,
    )
    assert posted.status_code == 200
    events = _notifications_for(task_id)
    assert any(e["event_type"] == "flow.test" for e in events)
