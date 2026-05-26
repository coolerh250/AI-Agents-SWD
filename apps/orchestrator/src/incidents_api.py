"""Incident API helpers used by the orchestrator FastAPI app.

Kept in its own module so the route bodies in ``main.py`` stay short and the
audit / notification side-effects are testable in isolation.
"""

import contextlib
from typing import Any

from shared.sdk.http_clients.audit_http_client import AuditHttpClient
from shared.sdk.incidents import IncidentStore
from shared.sdk.incidents.models import Incident, normalize_severity
from shared.sdk.notifications.client import send_notification


async def create_incident_with_side_effects(
    store: IncidentStore,
    *,
    severity: str,
    source: str,
    summary: str,
    task_id: str | None = None,
    workflow_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> Incident:
    """Insert an incident row, then publish notification + audit (best-effort)."""
    incident = await store.create_incident(
        severity=normalize_severity(severity),
        source=source,
        summary=summary,
        task_id=task_id,
        workflow_id=workflow_id,
        details=details or {},
    )
    await _publish_notification(incident, "incident.created", summary)
    await _record_audit(
        incident,
        decision_type="incident_created",
        result="open",
        summary=summary,
    )
    return incident


async def ack_incident_with_side_effects(store: IncidentStore, incident_id: str) -> Incident | None:
    incident = await store.ack_incident(incident_id)
    if incident is None:
        return None
    await _publish_notification(
        incident, "incident.acknowledged", f"incident {incident.incident_id} acknowledged"
    )
    await _record_audit(
        incident,
        decision_type="incident_acknowledged",
        result="acknowledged",
        summary=incident.summary,
    )
    return incident


async def resolve_incident_with_side_effects(
    store: IncidentStore, incident_id: str
) -> Incident | None:
    incident = await store.resolve_incident(incident_id)
    if incident is None:
        return None
    await _publish_notification(
        incident, "incident.resolved", f"incident {incident.incident_id} resolved"
    )
    await _record_audit(
        incident,
        decision_type="incident_resolved",
        result="resolved",
        summary=incident.summary,
    )
    return incident


async def _publish_notification(incident: Incident, event_type: str, message: str) -> None:
    # task_id is the canonical correlation key for stream.notifications. Fall
    # back to the incident_id so an operator-created incident with no
    # associated workflow still produces a routable notification.
    correlation_id = incident.task_id or incident.incident_id
    with contextlib.suppress(Exception):
        await send_notification(correlation_id, event_type, message)


async def _record_audit(
    incident: Incident,
    *,
    decision_type: str,
    result: str,
    summary: str,
) -> None:
    audit = AuditHttpClient()
    with contextlib.suppress(Exception):
        await audit.record_event(
            task_id=incident.task_id or incident.incident_id,
            agent="orchestrator",
            decision_type=decision_type,
            summary=summary,
            result=result,
            artifact_refs={
                "incident_id": incident.incident_id,
                "severity": incident.severity,
                "source": incident.source,
                "workflow_id": incident.workflow_id or "",
            },
            workflow_id=incident.workflow_id or "",
        )
