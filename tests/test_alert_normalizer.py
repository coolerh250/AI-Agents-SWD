"""Stage 40 -- alert normalizer tests."""

from shared.sdk.incidents.normalizer import (
    SOURCE_TYPE_ALERTMANAGER,
    SOURCE_TYPE_GENERIC,
    SOURCE_TYPE_SYNTHETIC,
    normalize_alertmanager_alert,
    normalize_generic_alert,
)
from shared.sdk.incidents.severity import SEV1_CRITICAL, SEV3_MEDIUM, SEV4_LOW


def _alertmanager_payload(severity: str = "critical", alert_name: str = "HostDown") -> dict:
    return {
        "status": "firing",
        "labels": {"alertname": alert_name, "severity": severity, "instance": "host1"},
        "annotations": {"summary": "host is down"},
        "startsAt": "2026-06-01T00:00:00Z",
        "endsAt": "0001-01-01T00:00:00Z",
        "fingerprint": "abc123",
    }


def test_alertmanager_normalize_critical():
    alert = normalize_alertmanager_alert(_alertmanager_payload("critical"))
    assert alert.normalized_severity == SEV1_CRITICAL
    assert alert.alert_name == "HostDown"
    assert alert.source_type == SOURCE_TYPE_ALERTMANAGER
    assert alert.fingerprint == "abc123"


def test_alertmanager_normalize_warning():
    alert = normalize_alertmanager_alert(_alertmanager_payload("warning", "HighLatency"))
    assert alert.normalized_severity == SEV3_MEDIUM
    assert alert.alert_name == "HighLatency"


def test_alertmanager_unknown_severity_defaults_to_medium():
    alert = normalize_alertmanager_alert(_alertmanager_payload("", "Nameless"))
    assert alert.normalized_severity == SEV3_MEDIUM


def test_generic_alert_normalize():
    payload = {
        "source": "synthetic_test",
        "alert_name": "orchestrator_down",
        "severity": "critical",
        "labels": {"component": "orchestrator"},
        "annotations": {"runbook": "https://example.com"},
        "fingerprint": "fp42",
        "starts_at": "2026-06-01T00:00:00Z",
    }
    alert = normalize_generic_alert(payload)
    assert alert.normalized_severity == SEV1_CRITICAL
    assert alert.alert_name == "orchestrator_down"
    assert alert.source_type == SOURCE_TYPE_SYNTHETIC
    assert alert.fingerprint == "fp42"


def test_generic_alert_unknown_severity():
    payload = {"source": "test", "alert_name": "weird", "severity": "???"}
    alert = normalize_generic_alert(payload)
    assert alert.normalized_severity == SEV4_LOW


def test_generic_alert_non_synthetic_source():
    payload = {"source": "grafana", "alert_name": "alert1", "severity": "info"}
    alert = normalize_generic_alert(payload)
    assert alert.source_type == SOURCE_TYPE_GENERIC
