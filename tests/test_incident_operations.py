"""Stage 40 -- structural tests for operations.py incident endpoints."""

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_operations() -> str:
    return (_REPO_ROOT / "apps" / "orchestrator" / "src" / "operations.py").read_text(
        encoding="utf-8"
    )


def test_incidents_list_endpoint():
    src = _read_operations()
    assert '@router.get("/incidents")' in src


def test_incident_detail_endpoint():
    src = _read_operations()
    assert '@router.get("/incidents/{incident_id}")' in src


def test_incident_timeline_endpoint():
    src = _read_operations()
    assert '@router.get("/incidents/{incident_id}/timeline")' in src


def test_incident_alerts_endpoint():
    src = _read_operations()
    assert '@router.get("/incidents/{incident_id}/alerts")' in src


def test_incident_acknowledge_endpoint():
    src = _read_operations()
    assert '@router.post("/incidents/{incident_id}/acknowledge")' in src


def test_incident_resolve_endpoint():
    src = _read_operations()
    assert '@router.post("/incidents/{incident_id}/resolve")' in src


def test_incident_close_endpoint():
    src = _read_operations()
    assert '@router.post("/incidents/{incident_id}/close")' in src


def test_incident_reopen_endpoint():
    src = _read_operations()
    assert '@router.post("/incidents/{incident_id}/reopen")' in src


def test_incident_postmortem_endpoint():
    src = _read_operations()
    assert '@router.post("/incidents/{incident_id}/postmortem")' in src


def test_postmortems_list_endpoint():
    src = _read_operations()
    assert '@router.get("/incidents/postmortems")' in src


def test_postmortem_detail_endpoint():
    src = _read_operations()
    assert '@router.get("/incidents/postmortems/{postmortem_id}")' in src


def test_safety_carries_stage40_incident_fields():
    src = _read_operations()
    required_fields = (
        '"incident_response_enabled"',
        '"external_alert_receiver_enabled"',
        '"external_alert_receiver_authenticated"',
        '"incident_escalation_dry_run"',
        '"real_incident_escalation_enabled"',
        '"incident_auto_remediation_enabled"',
        '"incident_sev1_open_count"',
        '"incident_open_count"',
        '"incident_postmortem_required_count"',
        '"alert_receiver_last_event_at"',
        '"alert_receiver_rejected_total"',
    )
    for field in required_fields:
        assert field in src, f"missing safety field: {field}"


def test_no_real_escalation_in_operations():
    src = _read_operations()
    assert "real_incident_escalation_enabled" in src
    assert '"real_incident_escalation_enabled": False' in src


def test_no_auto_remediation_in_operations():
    src = _read_operations()
    assert '"incident_auto_remediation_enabled": False' in src
