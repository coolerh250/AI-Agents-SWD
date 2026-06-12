"""Stage 40 -- alert receiver integration flow structural test (no real DB)."""

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_receiver() -> str:
    return (_REPO_ROOT / "apps" / "orchestrator" / "src" / "alert_receiver.py").read_text(
        encoding="utf-8"
    )


def test_intake_function_exists():
    src = _read_receiver()
    assert "_intake_alert" in src


def test_intake_calls_dedupe():
    src = _read_receiver()
    assert "compute_dedupe_key" in src or "find_open_incident_by_dedupe" in src


def test_intake_creates_incident():
    src = _read_receiver()
    assert "create_incident" in src


def test_intake_creates_lifecycle_event():
    src = _read_receiver()
    assert "lifecycle_store" in src or "record_event" in src


def test_intake_writes_audit_event():
    src = _read_receiver()
    assert "_record_audit" in src


def test_intake_writes_notification():
    src = _read_receiver()
    assert "send_notification" in src


def test_dedupe_links_to_existing_incident():
    src = _read_receiver()
    assert "existing_incident_id" in src or "find_open_incident_by_dedupe" in src


def test_no_secret_in_response():
    src = _read_receiver()
    assert "dry_run" in src
    assert "production_executed" in src
    # Ensure raw secret fields are never returned
    assert "raw_secret" not in src
    assert "HMAC key" not in src


def test_rejected_payload_increments_metric():
    src = _read_receiver()
    assert "INCIDENT_ALERTS_REJECTED_TOTAL" in src
