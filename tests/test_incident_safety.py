"""Stage 40 -- incident safety constraints structural tests."""

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_operations() -> str:
    return (_REPO_ROOT / "apps" / "orchestrator" / "src" / "operations.py").read_text(
        encoding="utf-8"
    )


def _read_receiver() -> str:
    return (_REPO_ROOT / "apps" / "orchestrator" / "src" / "alert_receiver.py").read_text(
        encoding="utf-8"
    )


def test_no_real_escalation_in_codebase():
    """No real pager/Slack/OpsGenie *send call* should be present in the receiver."""
    # alert_receiver.py must not make real external calls
    src = _read_receiver()
    for forbidden in ("oncall.send", "slack.post_message", "pagerduty.trigger", "opsgenie.create_alert"):
        assert forbidden not in src.lower(), f"alert_receiver.py: must not contain {forbidden!r}"


def test_auto_remediation_disabled():
    src = _read_operations()
    assert '"incident_auto_remediation_enabled": False' in src


def test_real_escalation_disabled():
    src = _read_operations()
    assert '"real_incident_escalation_enabled": False' in src


def test_dry_run_escalation_enabled():
    src = _read_operations()
    assert '"incident_escalation_dry_run": True' in src


def test_receiver_auth_field_present():
    src = _read_operations()
    assert '"external_alert_receiver_authenticated"' in src


def test_receiver_does_not_write_secret_to_repo():
    import re
    src = _read_receiver()
    # Only flag lines that assign a *string literal* to a secret-sounding variable.
    # Legitimate code like `secret = _shared_secret()` (env read) is fine.
    lines_with_hardcoded_secret = [
        line for line in src.splitlines()
        if re.search(r'\bsecret\b\s*=\s*["\']', line, re.IGNORECASE)
        and not line.strip().startswith("#")
        and "ALERT_RECEIVER_SHARED_SECRET" not in line
    ]
    assert not lines_with_hardcoded_secret, f"possible hardcoded secret: {lines_with_hardcoded_secret}"


def test_production_executed_false_in_receiver():
    src = _read_receiver()
    assert '"production_executed": False' in src


def test_audit_events_have_production_executed_false():
    from shared.sdk.incidents.audit_events import safe_incident_artifact_refs

    refs = safe_incident_artifact_refs()
    assert refs["production_executed"] is False
