"""Stage 40 -- deduplification key computation tests."""

from shared.sdk.incidents.dedupe import compute_dedupe_key, is_incident_open


def test_dedupe_key_stable():
    k1 = compute_dedupe_key(
        source="alertmanager",
        alert_name="HostDown",
        fingerprint="fp1",
        labels={"severity": "critical", "instance": "host1"},
    )
    k2 = compute_dedupe_key(
        source="alertmanager",
        alert_name="HostDown",
        fingerprint="fp1",
        labels={"instance": "host1", "severity": "critical"},
    )
    assert k1 == k2


def test_dedupe_key_different_for_different_sources():
    k1 = compute_dedupe_key(source="am1", alert_name="A", fingerprint="fp", labels={})
    k2 = compute_dedupe_key(source="am2", alert_name="A", fingerprint="fp", labels={})
    assert k1 != k2


def test_dedupe_key_different_for_different_fingerprint():
    k1 = compute_dedupe_key(source="am", alert_name="A", fingerprint="fp1", labels={})
    k2 = compute_dedupe_key(source="am", alert_name="A", fingerprint="fp2", labels={})
    assert k1 != k2


def test_dedupe_key_none_fingerprint():
    k = compute_dedupe_key(source="am", alert_name="A", fingerprint=None, labels={})
    assert isinstance(k, str) and len(k) == 64


def test_is_incident_open_statuses():
    assert is_incident_open("open") is True
    assert is_incident_open("acknowledged") is True
    assert is_incident_open("investigating") is True
    assert is_incident_open("resolved") is False
    assert is_incident_open("closed") is False
    assert is_incident_open(None) is False
