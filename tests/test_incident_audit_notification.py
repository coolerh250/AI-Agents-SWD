"""Stage 40 -- audit and notification event constants tests."""

from shared.sdk.incidents.audit_events import (
    DECISION_INCIDENT_ACKNOWLEDGED,
    DECISION_INCIDENT_ALERT_RECEIVED,
    DECISION_INCIDENT_ALERT_REJECTED,
    DECISION_INCIDENT_CLOSED,
    DECISION_INCIDENT_CREATED,
    DECISION_INCIDENT_DEDUPLICATED,
    DECISION_INCIDENT_ESCALATION_DRY_RUN,
    DECISION_INCIDENT_POSTMORTEM_COMPLETED,
    DECISION_INCIDENT_POSTMORTEM_CREATED,
    DECISION_INCIDENT_REOPENED,
    DECISION_INCIDENT_RESOLVED,
    EVENT_INCIDENT_ACKNOWLEDGED,
    EVENT_INCIDENT_ALERT_RECEIVED,
    EVENT_INCIDENT_CLOSED,
    EVENT_INCIDENT_CREATED,
    EVENT_INCIDENT_ESCALATION_DRY_RUN,
    EVENT_INCIDENT_POSTMORTEM_REQUIRED,
    EVENT_INCIDENT_RESOLVED,
    safe_incident_artifact_refs,
)


def test_audit_decision_types_defined():
    assert DECISION_INCIDENT_ALERT_RECEIVED == "incident_alert_received"
    assert DECISION_INCIDENT_ALERT_REJECTED == "incident_alert_rejected"
    assert DECISION_INCIDENT_CREATED == "incident_created"
    assert DECISION_INCIDENT_ACKNOWLEDGED == "incident_acknowledged"
    assert DECISION_INCIDENT_ESCALATION_DRY_RUN == "incident_escalation_dry_run"
    assert DECISION_INCIDENT_RESOLVED == "incident_resolved"
    assert DECISION_INCIDENT_CLOSED == "incident_closed"
    assert DECISION_INCIDENT_REOPENED == "incident_reopened"
    assert DECISION_INCIDENT_POSTMORTEM_CREATED == "incident_postmortem_created"
    assert DECISION_INCIDENT_POSTMORTEM_COMPLETED == "incident_postmortem_completed"


def test_notification_events_use_dot_format():
    for evt in (
        EVENT_INCIDENT_ALERT_RECEIVED,
        EVENT_INCIDENT_CREATED,
        EVENT_INCIDENT_ACKNOWLEDGED,
        EVENT_INCIDENT_ESCALATION_DRY_RUN,
        EVENT_INCIDENT_RESOLVED,
        EVENT_INCIDENT_CLOSED,
        EVENT_INCIDENT_POSTMORTEM_REQUIRED,
    ):
        assert evt.startswith("incident."), f"notification event should start with 'incident.': {evt}"


def test_safe_artifact_refs_never_exposes_key_bytes():
    refs = safe_incident_artifact_refs(
        incident_id="inc-1",
        alert_id="alert-1",
        severity="SEV1_CRITICAL",
        source="alertmanager",
        dedupe_key_hash="abc123def456",
        dry_run=True,
    )
    assert refs["production_executed"] is False
    assert refs["dry_run"] is True
    assert "incident_id" in refs
    forbidden = ("api_key", "secret_value", "token_value", "raw_password", "hmac_key")
    for term in forbidden:
        assert term not in str(refs).lower(), f"artifact_refs must not contain {term!r}"


def test_safe_artifact_refs_truncates_dedupe_hash():
    refs = safe_incident_artifact_refs(
        dedupe_key_hash="abcdef1234567890abcdef1234567890abcdef12",
    )
    # Only first 16 chars + ... should appear, not the full hash
    assert len(refs.get("dedupe_key_hash", "")) <= 20
