import uuid

import pytest
from fastapi.testclient import TestClient

_DB_SKIP = "no reachable PostgreSQL; skipping approval-engine persistence test"


def _create(client: TestClient, action: str) -> dict:
    response = client.post(
        "/approval/request",
        json={
            "task_id": f"test-approval-{uuid.uuid4().hex[:8]}",
            "action": action,
            "risk_level": "high",
            "reason": "pytest governance test",
            "requested_by": "pytest",
        },
    )
    if response.status_code == 503:
        pytest.skip(_DB_SKIP)
    assert response.status_code == 200, response.text
    return response.json()


def test_health(approval_engine_app):
    client = TestClient(approval_engine_app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_request_create_and_get(approval_engine_app):
    client = TestClient(approval_engine_app)
    created = _create(client, "production.deploy")
    assert created["status"] == "pending"
    assert created["action"] == "production.deploy"
    assert created["request_id"]

    got = client.get(f"/approval/{created['request_id']}")
    assert got.status_code == 200
    body = got.json()
    assert body["request_id"] == created["request_id"]
    assert body["task_id"] == created["task_id"]
    assert body["status"] == "pending"


def test_request_approve(approval_engine_app):
    client = TestClient(approval_engine_app)
    created = _create(client, "production.deploy")
    approved = client.post(
        "/approval/approve",
        json={"request_id": created["request_id"], "decided_by": "pytest"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["decided_by"] == "pytest"


def test_request_reject(approval_engine_app):
    client = TestClient(approval_engine_app)
    created = _create(client, "secret.rotation")
    rejected = client.post(
        "/approval/reject",
        json={"request_id": created["request_id"], "decided_by": "pytest"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"


def test_get_unknown_request_returns_404(approval_engine_app):
    client = TestClient(approval_engine_app)
    response = client.get(f"/approval/{uuid.uuid4()}")
    if response.status_code == 503:
        pytest.skip(_DB_SKIP)
    assert response.status_code == 404
