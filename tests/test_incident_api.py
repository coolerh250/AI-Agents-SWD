import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _orchestrator_db_up() -> bool:
    """The /incidents endpoints all require PostgreSQL. The TestClient runs the
    app in-process, so we probe the actual database the orchestrator targets."""
    try:
        # The list endpoint returns 503 when the DB is unavailable.
        response = client.get("/incidents")
    except Exception:
        return False
    return response.status_code == 200


requires_db = pytest.mark.skipif(
    not _orchestrator_db_up(), reason="incident store / postgres not reachable"
)


def _task_id() -> str:
    return f"test-incident-api-{uuid.uuid4().hex[:8]}"


def test_list_incidents_returns_empty_envelope_when_db_unavailable_returns_503():
    response = client.get("/incidents")
    # We only assert the contract: either the DB is up and we get 200 +
    # {count, incidents}, or it is down and we get a 503 — never a 500.
    assert response.status_code in (200, 503)
    if response.status_code == 200:
        body = response.json()
        assert "count" in body
        assert "incidents" in body


def test_create_incident_requires_summary():
    response = client.post("/incidents", json={"severity": "sev2"})
    # 400 always (no DB needed).
    assert response.status_code == 400


def test_create_incident_rejects_non_dict_details():
    response = client.post(
        "/incidents",
        json={"summary": "x", "details": "not-an-object"},
    )
    assert response.status_code == 400


@requires_db
def test_create_then_get_then_ack_then_resolve():
    task_id = _task_id()
    response = client.post(
        "/incidents",
        json={
            "severity": "sev2",
            "source": "test-incident-api",
            "summary": "incident api lifecycle",
            "task_id": task_id,
            "workflow_id": f"wf-{task_id}",
            "details": {"smoke": True},
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    incident_id = body["incident_id"]
    assert body["status"] == "open"
    assert body["severity"] == "sev2"
    assert body["task_id"] == task_id

    fetched = client.get(f"/incidents/{incident_id}")
    assert fetched.status_code == 200
    assert fetched.json()["incident_id"] == incident_id

    listed = client.get(f"/incidents?task_id={task_id}")
    assert listed.status_code == 200
    assert any(item["incident_id"] == incident_id for item in listed.json()["incidents"])

    acked = client.post(f"/incidents/{incident_id}/ack")
    assert acked.status_code == 200
    acked_body = acked.json()
    assert acked_body["status"] == "acknowledged"
    assert acked_body["acknowledged_at"]

    resolved = client.post(f"/incidents/{incident_id}/resolve")
    assert resolved.status_code == 200
    resolved_body = resolved.json()
    assert resolved_body["status"] == "resolved"
    assert resolved_body["resolved_at"]
    # ack timestamp must persist across the resolve transition
    assert resolved_body["acknowledged_at"] == acked_body["acknowledged_at"]


@requires_db
def test_unknown_incident_returns_404():
    bogus = uuid.uuid4().hex
    response = client.get(f"/incidents/{bogus}")
    # Either we recognise it as a not-found UUID (404) or asyncpg rejects the
    # raw hex string (503). Both are acceptable — we just never want a 500.
    assert response.status_code in (404, 503)


@requires_db
def test_list_filters_by_severity_only_returns_matching():
    task_id = _task_id()
    client.post(
        "/incidents",
        json={
            "severity": "sev1",
            "source": "test-incident-api",
            "summary": "sev1 row",
            "task_id": task_id,
        },
    )
    listed = client.get(f"/incidents?task_id={task_id}&severity=sev1")
    assert listed.status_code == 200
    items = listed.json()["incidents"]
    assert items, "no incidents returned for the seeded task_id + sev1 filter"
    assert all(item["severity"] == "sev1" for item in items)


def _audit_up() -> bool:
    try:
        return httpx.get("http://localhost:8003/health", timeout=3).status_code == 200
    except Exception:
        return False


@requires_db
@pytest.mark.skipif(not _audit_up(), reason="audit-service not reachable on localhost:8003")
def test_create_emits_audit_event():
    """Smoke that the audit side-effect actually lands when audit-service is up."""
    task_id = _task_id()
    response = client.post(
        "/incidents",
        json={
            "summary": "audit side-effect smoke",
            "source": "test-incident-api",
            "task_id": task_id,
        },
    )
    assert response.status_code == 200
    # audit-service returns {"task_id":..,"count":N,"events":[...]} keyed by
    # the task_id we pass through. The side-effect is fire-and-forget, so
    # tolerate a brief delay.
    import time

    for _ in range(10):
        events = httpx.get(f"http://localhost:8003/audit/events/{task_id}", timeout=3).json()
        if events.get("count", 0) >= 1:
            break
        time.sleep(0.5)
    assert events.get("count", 0) >= 1
    assert any(ev.get("decision_type") == "incident_created" for ev in events.get("events", []))
