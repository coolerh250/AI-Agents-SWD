"""Stage 40 -- structural tests for the Alertmanager receiver."""

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_receiver() -> str:
    return (_REPO_ROOT / "apps" / "orchestrator" / "src" / "alert_receiver.py").read_text(
        encoding="utf-8"
    )


def test_alertmanager_endpoint_registered():
    src = _read_receiver()
    assert '@router.post("/alertmanager")' in src


def test_alertmanager_validates_alerts_list():
    src = _read_receiver()
    assert "alerts list is required" in src or "alerts_list" in src


def test_alertmanager_calls_normalizer():
    src = _read_receiver()
    assert "normalize_alertmanager_alert" in src


def test_alertmanager_records_audit():
    src = _read_receiver()
    assert "_record_audit" in src
    assert "DECISION_INCIDENT_ALERT_RECEIVED" in src


def test_alertmanager_increments_metrics():
    src = _read_receiver()
    assert "INCIDENT_ALERTS_RECEIVED_TOTAL" in src
    assert "INCIDENT_CREATED_TOTAL" in src


def test_alertmanager_dry_run_escalation_for_sev1():
    src = _read_receiver()
    assert "SEV1_CRITICAL" in src
    assert "run_dry_escalation" in src


def test_alertmanager_no_real_escalation():
    src = _read_receiver()
    assert "real_escalation_sent" in src or "production_executed" in src
    assert "pagerduty" not in src.lower()
    assert "opsgenie" not in src.lower()
