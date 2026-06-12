"""Stage 40 -- audit decision_type constants and notification event names."""

# Audit decision types for audit_logs
DECISION_INCIDENT_ALERT_RECEIVED = "incident_alert_received"
DECISION_INCIDENT_ALERT_REJECTED = "incident_alert_rejected"
DECISION_INCIDENT_CREATED = "incident_created"
DECISION_INCIDENT_DEDUPLICATED = "incident_deduplicated"
DECISION_INCIDENT_ACKNOWLEDGED = "incident_acknowledged"
DECISION_INCIDENT_ESCALATION_DRY_RUN = "incident_escalation_dry_run"
DECISION_INCIDENT_RESOLVED = "incident_resolved"
DECISION_INCIDENT_CLOSED = "incident_closed"
DECISION_INCIDENT_REOPENED = "incident_reopened"
DECISION_INCIDENT_POSTMORTEM_CREATED = "incident_postmortem_created"
DECISION_INCIDENT_POSTMORTEM_COMPLETED = "incident_postmortem_completed"

# Notification event names (all kept in DEFAULT_REAL_DELIVERY_DENYLIST)
EVENT_INCIDENT_ALERT_RECEIVED = "incident.alert_received"
EVENT_INCIDENT_CREATED = "incident.created"
EVENT_INCIDENT_ACKNOWLEDGED = "incident.acknowledged"
EVENT_INCIDENT_ESCALATION_DRY_RUN = "incident.escalation_dry_run"
EVENT_INCIDENT_RESOLVED = "incident.resolved"
EVENT_INCIDENT_CLOSED = "incident.closed"
EVENT_INCIDENT_POSTMORTEM_REQUIRED = "incident.postmortem_required"


def safe_incident_artifact_refs(
    *,
    incident_id: str | None = None,
    alert_id: str | None = None,
    severity: str | None = None,
    source: str | None = None,
    dedupe_key_hash: str | None = None,
    dry_run: bool = True,
    production_executed: bool = False,
) -> dict:
    """Build artifact_refs safe for audit rows — never includes raw secrets."""
    refs: dict = {"production_executed": False, "dry_run": dry_run}
    if incident_id:
        refs["incident_id"] = incident_id
    if alert_id:
        refs["alert_id"] = alert_id
    if severity:
        refs["severity"] = severity
    if source:
        refs["source"] = source
    if dedupe_key_hash:
        refs["dedupe_key_hash"] = dedupe_key_hash[:16] + "..."
    return refs


__all__ = [
    "DECISION_INCIDENT_ALERT_RECEIVED",
    "DECISION_INCIDENT_ALERT_REJECTED",
    "DECISION_INCIDENT_CREATED",
    "DECISION_INCIDENT_DEDUPLICATED",
    "DECISION_INCIDENT_ACKNOWLEDGED",
    "DECISION_INCIDENT_ESCALATION_DRY_RUN",
    "DECISION_INCIDENT_RESOLVED",
    "DECISION_INCIDENT_CLOSED",
    "DECISION_INCIDENT_REOPENED",
    "DECISION_INCIDENT_POSTMORTEM_CREATED",
    "DECISION_INCIDENT_POSTMORTEM_COMPLETED",
    "EVENT_INCIDENT_ALERT_RECEIVED",
    "EVENT_INCIDENT_CREATED",
    "EVENT_INCIDENT_ACKNOWLEDGED",
    "EVENT_INCIDENT_ESCALATION_DRY_RUN",
    "EVENT_INCIDENT_RESOLVED",
    "EVENT_INCIDENT_CLOSED",
    "EVENT_INCIDENT_POSTMORTEM_REQUIRED",
    "safe_incident_artifact_refs",
]
