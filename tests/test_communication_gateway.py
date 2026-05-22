import uuid

import httpx
import pytest
from fastapi.testclient import TestClient


def _orchestrator_up() -> bool:
    try:
        return httpx.get("http://localhost:8000/health", timeout=3).status_code == 200
    except Exception:
        return False


# /intake, /tasks and /notifications need the orchestrator + Redis reachable.
requires_stack = pytest.mark.skipif(
    not _orchestrator_up(), reason="orchestrator not reachable on localhost:8000"
)


def test_health(communication_gateway_app):
    response = TestClient(communication_gateway_app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@requires_stack
def test_intake_mock_non_production(communication_gateway_app):
    client = TestClient(communication_gateway_app)
    task_id = f"test-gw-dev-{uuid.uuid4().hex[:8]}"
    response = client.post(
        "/intake/mock", json={"task_id": task_id, "request": {"type": "dev.test"}}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == task_id
    assert body["stage"] == "completed"
    assert body["approval_required"] is False


@requires_stack
def test_intake_mock_production_deploy(communication_gateway_app):
    client = TestClient(communication_gateway_app)
    task_id = f"test-gw-prod-{uuid.uuid4().hex[:8]}"
    response = client.post(
        "/intake/mock", json={"task_id": task_id, "request": {"type": "production.deploy"}}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["approval_required"] is True
    assert body["stage"] == "waiting_approval"
    assert body["workflow_result"]["execution_result"]["production_executed"] is False


@requires_stack
def test_get_task_returns_persisted_state(communication_gateway_app):
    client = TestClient(communication_gateway_app)
    task_id = f"test-gw-task-{uuid.uuid4().hex[:8]}"
    client.post("/intake/mock", json={"task_id": task_id, "request": {"type": "dev.test"}})
    response = client.get(f"/tasks/{task_id}")
    assert response.status_code == 200
    assert response.json()["task_id"] == task_id


@requires_stack
def test_notifications_test_and_list(communication_gateway_app):
    client = TestClient(communication_gateway_app)
    task_id = f"test-gw-notif-{uuid.uuid4().hex[:8]}"
    posted = client.post(
        "/notifications/test",
        json={"task_id": task_id, "event_type": "gateway.test", "message": "hi"},
    )
    assert posted.status_code == 200
    assert posted.json()["notification"]["task_id"] == task_id

    listed = client.get("/notifications?count=50")
    assert listed.status_code == 200
    body = listed.json()
    assert any(n["notification"].get("task_id") == task_id for n in body["notifications"])
