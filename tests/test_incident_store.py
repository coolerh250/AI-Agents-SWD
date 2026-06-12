import uuid

import pytest

from shared.sdk.incidents import IncidentStore
from shared.sdk.incidents.models import (
    INCIDENT_SEVERITIES,
    INCIDENT_STATUSES,
    normalize_severity,
    normalize_status,
)

_DB_SKIP = "no reachable PostgreSQL; skipping incident store test"


async def _store_or_skip() -> IncidentStore:
    store = IncidentStore()
    try:
        await store.list_incidents(limit=1)
    except Exception:
        pytest.skip(_DB_SKIP)
    return store


def _task_id() -> str:
    return f"test-incident-{uuid.uuid4().hex[:8]}"


def test_severity_and_status_constants_match_spec():
    assert INCIDENT_SEVERITIES == ("sev1", "sev2", "sev3", "sev4")
    # Stage 40 extended statuses; verify all required values are present
    for status in ("open", "acknowledged", "resolved", "closed", "investigating", "mitigated", "reopened"):
        assert status in INCIDENT_STATUSES, f"missing status: {status}"


def test_normalize_severity_coerces_unknown_to_sev3():
    assert normalize_severity("SEV1") == "sev1"
    assert normalize_severity("") == "sev3"
    assert normalize_severity(None) == "sev3"
    assert normalize_severity("low") == "sev3"


def test_normalize_status_coerces_unknown_to_open():
    assert normalize_status("ACKNOWLEDGED") == "acknowledged"
    assert normalize_status("") == "open"
    assert normalize_status(None) == "open"
    # "closed" is now a valid status (Stage 40), so it should pass through
    assert normalize_status("closed") == "closed"


async def test_create_get_list_incident():
    store = await _store_or_skip()
    task_id = _task_id()
    created = await store.create_incident(
        severity="sev2",
        source="test",
        summary="incident store create smoke",
        task_id=task_id,
        workflow_id=f"wf-{task_id}",
        details={"smoke": True, "retry_count": 3},
    )
    assert created.incident_id
    assert created.severity == "sev2"
    assert created.status == "open"
    assert created.task_id == task_id
    assert created.workflow_id == f"wf-{task_id}"
    assert created.details["retry_count"] == 3
    assert created.created_at

    fetched = await store.get_incident(created.incident_id)
    assert fetched is not None
    assert fetched.incident_id == created.incident_id
    assert fetched.task_id == task_id

    listed = await store.list_incidents(task_id=task_id)
    assert any(item.incident_id == created.incident_id for item in listed)


async def test_ack_then_resolve_incident():
    store = await _store_or_skip()
    task_id = _task_id()
    created = await store.create_incident(
        severity="sev3",
        source="test",
        summary="incident store lifecycle",
        task_id=task_id,
    )
    acked = await store.ack_incident(created.incident_id)
    assert acked is not None
    assert acked.status == "acknowledged"
    assert acked.acknowledged_at is not None

    resolved = await store.resolve_incident(created.incident_id)
    assert resolved is not None
    assert resolved.status == "resolved"
    assert resolved.resolved_at is not None
    # ack timestamp must NOT be overwritten by the resolve transition
    assert resolved.acknowledged_at == acked.acknowledged_at


async def test_list_filters_by_status_and_severity():
    store = await _store_or_skip()
    task_id = _task_id()
    await store.create_incident(severity="sev1", source="test", summary="sev1 row", task_id=task_id)
    await store.create_incident(severity="sev4", source="test", summary="sev4 row", task_id=task_id)
    sev1_only = await store.list_incidents(task_id=task_id, severity="sev1")
    assert all(item.severity == "sev1" for item in sev1_only)
    open_only = await store.list_incidents(task_id=task_id, status="open")
    assert all(item.status == "open" for item in open_only)


async def test_unknown_severity_is_normalized_on_create():
    store = await _store_or_skip()
    task_id = _task_id()
    created = await store.create_incident(
        severity="bogus", source="test", summary="bogus severity", task_id=task_id
    )
    assert created.severity == "sev3"
