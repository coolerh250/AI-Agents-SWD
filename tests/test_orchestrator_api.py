import httpx
import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _policy_engine_up() -> bool:
    try:
        return httpx.get("http://localhost:8001/health", timeout=3).status_code == 200
    except Exception:
        return False


requires_policy_engine = pytest.mark.skipif(
    not _policy_engine_up(), reason="policy-engine not reachable on localhost:8001"
)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"service": "orchestrator", "status": "ok"}


@requires_policy_engine
def test_workflow_test_non_production():
    response = client.post(
        "/workflow/test",
        json={
            "task_id": "api-dev-1",
            "source": "test",
            "request": {"type": "dev.test", "description": "non-production"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["stage"] == "dispatched"
    assert body["approval_required"] is False


def test_workflow_test_production_deploy():
    response = client.post(
        "/workflow/test",
        json={
            "task_id": "api-prod-1",
            "source": "test",
            "request": {"type": "production.deploy", "description": "production deploy"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["approval_required"] is True
    assert body["stage"] == "waiting_approval"
    assert body["stage"] != "completed"


@requires_policy_engine
def test_workflow_policy_test():
    restricted = client.post("/workflow/policy-test", json={"type": "production.deploy"})
    assert restricted.status_code == 200
    assert restricted.json()["allowed"] is False
    assert restricted.json()["approval_required"] is True

    allowed = client.post("/workflow/policy-test", json={"type": "code.read"})
    assert allowed.json()["allowed"] is True
    assert allowed.json()["approval_required"] is False


def test_workflow_schema():
    response = client.get("/workflow/schema")
    assert response.status_code == 200
    schema = response.json()
    for field in ["task_id", "stage", "approval_required", "audit_refs", "execution_result"]:
        assert field in schema
