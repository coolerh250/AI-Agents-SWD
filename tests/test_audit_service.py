import uuid

import pytest
from fastapi.testclient import TestClient

_DB_SKIP = "no reachable PostgreSQL; skipping audit-service persistence test"


def test_health(audit_service_app):
    client = TestClient(audit_service_app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_event_insert_and_query(audit_service_app):
    client = TestClient(audit_service_app)
    task_id = f"test-audit-{uuid.uuid4().hex[:8]}"
    created = client.post(
        "/audit/events",
        json={
            "task_id": task_id,
            "agent": "pytest",
            "decision_type": "test",
            "summary": "audit-service insert test",
            "result": "ok",
            "artifact_refs": {"sample": "ref"},
        },
    )
    if created.status_code == 503:
        pytest.skip(_DB_SKIP)
    assert created.status_code == 200, created.text
    assert created.json()["audit_id"]

    queried = client.get(f"/audit/events/{task_id}")
    assert queried.status_code == 200
    body = queried.json()
    assert body["task_id"] == task_id
    assert body["count"] >= 1
    event = body["events"][0]
    assert event["agent"] == "pytest"
    assert event["decision_type"] == "test"
    assert event["result"] == "ok"
    assert event["artifact_refs"] == {"sample": "ref"}


def test_query_unknown_task_returns_empty(audit_service_app):
    client = TestClient(audit_service_app)
    response = client.get(f"/audit/events/missing-{uuid.uuid4().hex[:8]}")
    if response.status_code == 503:
        pytest.skip(_DB_SKIP)
    assert response.status_code == 200
    assert response.json()["count"] == 0
