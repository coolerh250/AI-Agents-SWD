"""Stage 40 -- External alert receiver endpoints.

Mounted at /alerts/* in the orchestrator.

Architecture: Option B (integrated into orchestrator) to avoid a new
container. The orchestrator already has DB access, audit, notification,
and metric infrastructure.

Security constraints:
- No real escalation is performed. All escalation paths are dry_run=true.
- ALERT_RECEIVER_SHARED_SECRET enables HMAC-header auth; when absent the
  service runs in local_test_unsigned mode and /operations/safety reports
  external_alert_receiver_authenticated=false.
- Raw payloads are always redacted before storage; only the SHA-256 hash
  of the original is stored.
- incident.* notification events exist in the DEFAULT_REAL_DELIVERY_DENYLIST.
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from shared.sdk.http_clients.audit_http_client import AuditHttpClient
from shared.sdk.incidents.alert_store import AlertStore
from shared.sdk.incidents.audit_events import (
    DECISION_INCIDENT_ALERT_RECEIVED,
    DECISION_INCIDENT_ALERT_REJECTED,
    DECISION_INCIDENT_CREATED,
    DECISION_INCIDENT_DEDUPLICATED,
    DECISION_INCIDENT_ESCALATION_DRY_RUN,
    EVENT_INCIDENT_ALERT_RECEIVED,
    EVENT_INCIDENT_CREATED,
    EVENT_INCIDENT_ESCALATION_DRY_RUN,
    EVENT_INCIDENT_POSTMORTEM_REQUIRED,
    safe_incident_artifact_refs,
)
from shared.sdk.incidents.dedupe import compute_dedupe_key
from shared.sdk.incidents.escalation import EscalationStore
from shared.sdk.incidents.lifecycle import (
    EVENT_INCIDENT_CREATED as LC_CREATED,
    EVENT_INCIDENT_LINKED_TO_ALERT,
    LifecycleStore,
)
from shared.sdk.incidents.normalizer import (
    NormalizedAlert,
    normalize_alertmanager_alert,
    normalize_generic_alert,
)
from shared.sdk.incidents.severity import SEV1_CRITICAL, SEV2_HIGH, postmortem_required
from shared.sdk.incidents.store import IncidentStore
from shared.sdk.notifications.client import send_notification
from shared.sdk.observability.metrics import (
    INCIDENT_ALERTS_RECEIVED_TOTAL,
    INCIDENT_ALERTS_REJECTED_TOTAL,
    INCIDENT_CREATED_TOTAL,
    INCIDENT_DEDUPLICATED_TOTAL,
    INCIDENT_ESCALATION_DRY_RUN_TOTAL,
    INCIDENT_POSTMORTEM_REQUIRED_TOTAL,
)

router = APIRouter(prefix="/alerts", tags=["alert-receiver"])


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------


def _shared_secret() -> str | None:
    return (os.environ.get("ALERT_RECEIVER_SHARED_SECRET", "") or "").strip() or None


def _check_auth(request: Request) -> None:
    """Validate X-AIAGENTS-ALERT-SIGNATURE when a shared secret is configured."""
    secret = _shared_secret()
    if secret is None:
        # local_test_unsigned mode: no auth check
        return
    sig_header = request.headers.get("X-AIAGENTS-ALERT-SIGNATURE", "")
    if not sig_header:
        INCIDENT_ALERTS_REJECTED_TOTAL.labels(reason="missing_signature").inc()
        raise HTTPException(status_code=401, detail="X-AIAGENTS-ALERT-SIGNATURE required")
    expected = hmac.new(
        secret.encode(), msg=sig_header.encode(), digestmod=hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, sig_header):
        INCIDENT_ALERTS_REJECTED_TOTAL.labels(reason="invalid_signature").inc()
        raise HTTPException(status_code=403, detail="invalid alert signature")


def receiver_auth_mode() -> str:
    return "local_test_unsigned" if _shared_secret() is None else "shared_secret"


def receiver_authenticated() -> bool:
    return _shared_secret() is not None


# ---------------------------------------------------------------------------
# Core intake logic
# ---------------------------------------------------------------------------


async def _intake_alert(
    alert: NormalizedAlert,
    *,
    raw_payload: Any,
) -> dict[str, Any]:
    """Persist alert, dedupe, create or link incident, dry-run escalation."""
    alert_store = AlertStore()
    incident_store = IncidentStore()
    lifecycle_store = LifecycleStore()
    escalation_store = EscalationStore()

    dedupe_key = compute_dedupe_key(
        source=alert.source,
        alert_name=alert.alert_name,
        fingerprint=alert.fingerprint,
        labels=alert.labels,
    )

    # Check for open incident with same dedupe_key
    existing_incident_id = await alert_store.find_open_incident_by_dedupe(dedupe_key)

    if existing_incident_id:
        # Deduplicate: link alert to existing incident
        alert_row = await alert_store.create_alert(
            alert,
            raw_payload=raw_payload,
            status="linked_to_incident",
            incident_id=existing_incident_id,
        )
        with contextlib.suppress(Exception):
            await lifecycle_store.record_event(
                incident_id=existing_incident_id,
                event_type=EVENT_INCIDENT_LINKED_TO_ALERT,
                metadata={"alert_id": alert_row["alert_id"], "dedupe_key": dedupe_key[:16]},
            )
        INCIDENT_DEDUPLICATED_TOTAL.labels(severity=alert.normalized_severity).inc()
        INCIDENT_ALERTS_RECEIVED_TOTAL.labels(
            source=alert.source, source_type=alert.source_type
        ).inc()
        with contextlib.suppress(Exception):
            await _record_audit(
                task_id=existing_incident_id,
                decision_type=DECISION_INCIDENT_DEDUPLICATED,
                result="deduplicated",
                summary=f"Alert {alert.alert_name} deduplicated to incident {existing_incident_id}",
                refs=safe_incident_artifact_refs(
                    incident_id=existing_incident_id,
                    alert_id=alert_row["alert_id"],
                    severity=alert.normalized_severity,
                    source=alert.source,
                    dedupe_key_hash=dedupe_key,
                ),
            )
        return {
            "action": "deduplicated",
            "alert_id": alert_row["alert_id"],
            "incident_id": existing_incident_id,
            "severity": alert.normalized_severity,
            "dry_run": True,
            "production_executed": False,
        }

    # Create new incident
    pm_req = postmortem_required(alert.normalized_severity)
    incident = await incident_store.create_incident(
        severity=alert.normalized_severity.lower().replace("_", "").replace("sev", "sev"),
        normalized_severity=alert.normalized_severity,
        source=alert.source,
        summary=f"[{alert.normalized_severity}] {alert.alert_name} from {alert.source}",
        postmortem_required=pm_req,
    )

    alert_row = await alert_store.create_alert(
        alert,
        raw_payload=raw_payload,
        status="linked_to_incident",
        incident_id=incident.incident_id,
    )

    with contextlib.suppress(Exception):
        await lifecycle_store.record_event(
            incident_id=incident.incident_id,
            event_type=LC_CREATED,
            new_status="open",
            metadata={
                "alert_id": alert_row["alert_id"],
                "severity": alert.normalized_severity,
                "source": alert.source,
            },
        )

    INCIDENT_ALERTS_RECEIVED_TOTAL.labels(source=alert.source, source_type=alert.source_type).inc()
    INCIDENT_CREATED_TOTAL.labels(severity=alert.normalized_severity, source=alert.source).inc()

    if pm_req:
        INCIDENT_POSTMORTEM_REQUIRED_TOTAL.labels(severity=alert.normalized_severity).inc()

    with contextlib.suppress(Exception):
        await _record_audit(
            task_id=incident.incident_id,
            decision_type=DECISION_INCIDENT_ALERT_RECEIVED,
            result="incident_created",
            summary=f"Alert {alert.alert_name} created incident {incident.incident_id}",
            refs=safe_incident_artifact_refs(
                incident_id=incident.incident_id,
                alert_id=alert_row["alert_id"],
                severity=alert.normalized_severity,
                source=alert.source,
                dedupe_key_hash=dedupe_key,
            ),
        )
    with contextlib.suppress(Exception):
        await _record_audit(
            task_id=incident.incident_id,
            decision_type=DECISION_INCIDENT_CREATED,
            result="open",
            summary=f"Incident {incident.incident_id} created [{alert.normalized_severity}]",
            refs=safe_incident_artifact_refs(
                incident_id=incident.incident_id,
                severity=alert.normalized_severity,
                source=alert.source,
                dry_run=True,
            ),
        )
    with contextlib.suppress(Exception):
        await send_notification(
            incident.incident_id, EVENT_INCIDENT_ALERT_RECEIVED, alert.alert_name
        )
    with contextlib.suppress(Exception):
        await send_notification(incident.incident_id, EVENT_INCIDENT_CREATED, incident.summary)

    # Dry-run escalation for SEV1 / SEV2
    escalation_result: dict[str, Any] = {}
    if alert.normalized_severity in (SEV1_CRITICAL, SEV2_HIGH):
        escalation_result = await escalation_store.run_dry_escalation(
            incident_id=incident.incident_id,
            severity=alert.normalized_severity,
            source=alert.source,
        )
        INCIDENT_ESCALATION_DRY_RUN_TOTAL.labels(
            severity=alert.normalized_severity, dry_run="true"
        ).inc()
        with contextlib.suppress(Exception):
            await lifecycle_store.record_event(
                incident_id=incident.incident_id,
                event_type="incident_escalated",
                metadata={**escalation_result, "dry_run": True},
            )
        with contextlib.suppress(Exception):
            await _record_audit(
                task_id=incident.incident_id,
                decision_type=DECISION_INCIDENT_ESCALATION_DRY_RUN,
                result="dry_run",
                summary=f"Escalation dry-run for {alert.normalized_severity} incident {incident.incident_id}",
                refs=safe_incident_artifact_refs(
                    incident_id=incident.incident_id,
                    severity=alert.normalized_severity,
                    dry_run=True,
                ),
            )
        with contextlib.suppress(Exception):
            await send_notification(
                incident.incident_id,
                EVENT_INCIDENT_ESCALATION_DRY_RUN,
                f"dry-run escalation for {alert.normalized_severity}",
            )
        if pm_req:
            with contextlib.suppress(Exception):
                await send_notification(
                    incident.incident_id,
                    EVENT_INCIDENT_POSTMORTEM_REQUIRED,
                    f"postmortem required for {incident.incident_id}",
                )

    return {
        "action": "created",
        "alert_id": alert_row["alert_id"],
        "incident_id": incident.incident_id,
        "severity": alert.normalized_severity,
        "postmortem_required": pm_req,
        "escalation": escalation_result or None,
        "dry_run": True,
        "production_executed": False,
    }


async def _record_audit(
    *,
    task_id: str,
    decision_type: str,
    result: str,
    summary: str,
    refs: dict | None = None,
) -> None:
    audit = AuditHttpClient()
    with contextlib.suppress(Exception):
        await audit.record_event(
            task_id=task_id,
            agent="alert-receiver",
            decision_type=decision_type,
            summary=summary,
            result=result,
            artifact_refs=refs or {},
            workflow_id="",
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/health")
async def alert_health() -> dict:
    return {
        "status": "ok",
        "receiver_enabled": True,
        "auth_mode": receiver_auth_mode(),
        "auth_required": _shared_secret() is not None,
        "external_alert_receiver_authenticated": receiver_authenticated(),
        "dry_run_escalation_enabled": True,
        "real_escalation_enabled": False,
        "production_executed": False,
        "generated_at": _utcnow_iso(),
    }


@router.post("/alertmanager")
async def receive_alertmanager(request: Request, payload: dict) -> dict:
    """Receive an Alertmanager webhook payload."""
    _check_auth(request)

    alerts_list = payload.get("alerts")
    if not isinstance(alerts_list, list) or not alerts_list:
        INCIDENT_ALERTS_REJECTED_TOTAL.labels(reason="malformed_payload").inc()
        with contextlib.suppress(Exception):
            await _record_audit(
                task_id="unknown",
                decision_type=DECISION_INCIDENT_ALERT_REJECTED,
                result="rejected",
                summary="Alertmanager payload rejected: missing or empty alerts list",
                refs={"reason": "malformed_payload", "production_executed": False},
            )
        raise HTTPException(status_code=400, detail="alerts list is required and must be non-empty")

    receiver = str(payload.get("receiver", "alertmanager")).strip() or "alertmanager"
    results: list[dict[str, Any]] = []

    for alert_obj in alerts_list:
        if not isinstance(alert_obj, dict):
            continue
        try:
            normalized = normalize_alertmanager_alert(alert_obj, receiver=receiver)
            result = await _intake_alert(normalized, raw_payload=alert_obj)
            results.append(result)
        except HTTPException:
            raise
        except Exception as exc:
            INCIDENT_ALERTS_REJECTED_TOTAL.labels(reason="processing_error").inc()
            results.append({"action": "error", "detail": str(exc)})

    return {
        "received": len(results),
        "results": results,
        "dry_run": True,
        "production_executed": False,
        "generated_at": _utcnow_iso(),
    }


@router.post("/generic")
async def receive_generic(request: Request, payload: dict) -> dict:
    """Receive a generic webhook alert payload."""
    _check_auth(request)

    alert_name = str((payload or {}).get("alert_name", "")).strip()
    if not alert_name:
        INCIDENT_ALERTS_REJECTED_TOTAL.labels(reason="malformed_payload").inc()
        raise HTTPException(status_code=400, detail="alert_name is required")

    try:
        normalized = normalize_generic_alert(payload)
        result = await _intake_alert(normalized, raw_payload=payload)
    except HTTPException:
        raise
    except Exception as exc:
        INCIDENT_ALERTS_REJECTED_TOTAL.labels(reason="processing_error").inc()
        raise HTTPException(status_code=503, detail=f"alert intake failed: {exc}") from exc

    return {
        **result,
        "generated_at": _utcnow_iso(),
    }
