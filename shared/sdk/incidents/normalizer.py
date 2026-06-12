"""Stage 40 -- alert payload normalisation.

Converts raw Alertmanager / generic webhook payloads into a uniform
``NormalizedAlert`` dataclass. Never stores or returns the raw payload;
callers must call ``redact_payload()`` from ``redaction.py`` before
persisting anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .severity import SEV3_MEDIUM, normalize_severity_v2

SOURCE_TYPE_ALERTMANAGER = "alertmanager"
SOURCE_TYPE_GENERIC = "generic_webhook"
SOURCE_TYPE_SYNTHETIC = "synthetic_test"


@dataclass
class NormalizedAlert:
    source: str
    source_type: str
    alert_name: str
    severity: str
    normalized_severity: str
    labels: dict[str, Any]
    annotations: dict[str, Any]
    fingerprint: str | None
    starts_at: datetime | None
    ends_at: datetime | None
    external_alert_id: str | None = None
    raw_status: str = "firing"

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "source_type": self.source_type,
            "alert_name": self.alert_name,
            "severity": self.severity,
            "normalized_severity": self.normalized_severity,
            "labels": dict(self.labels),
            "annotations": dict(self.annotations),
            "fingerprint": self.fingerprint,
            "starts_at": self.starts_at.isoformat() if self.starts_at else None,
            "ends_at": self.ends_at.isoformat() if self.ends_at else None,
            "external_alert_id": self.external_alert_id,
            "raw_status": self.raw_status,
        }


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            dt = datetime.strptime(value, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def normalize_alertmanager_alert(
    alert: dict[str, Any],
    *,
    receiver: str = "alertmanager",
) -> NormalizedAlert:
    """Normalise a single alert object from an Alertmanager webhook payload."""
    labels: dict[str, Any] = dict(alert.get("labels") or {})
    annotations: dict[str, Any] = dict(alert.get("annotations") or {})
    alert_name = str(labels.get("alertname", "unknown_alert"))
    raw_severity = str(labels.get("severity", "")).strip()
    normalized = normalize_severity_v2(raw_severity) if raw_severity else SEV3_MEDIUM
    fingerprint = str(alert.get("fingerprint") or "").strip() or None
    starts_at = _parse_dt(alert.get("startsAt"))
    ends_at = _parse_dt(alert.get("endsAt"))
    raw_status = str(alert.get("status", "firing")).lower()
    return NormalizedAlert(
        source=receiver,
        source_type=SOURCE_TYPE_ALERTMANAGER,
        alert_name=alert_name,
        severity=raw_severity or "unknown",
        normalized_severity=normalized,
        labels=labels,
        annotations=annotations,
        fingerprint=fingerprint,
        starts_at=starts_at,
        ends_at=ends_at,
        raw_status=raw_status,
    )


def normalize_generic_alert(payload: dict[str, Any]) -> NormalizedAlert:
    """Normalise a generic webhook payload."""
    source = str(payload.get("source", "generic")).strip() or "generic"
    alert_name = str(payload.get("alert_name", "unknown_alert")).strip()
    raw_severity = str(payload.get("severity", "")).strip()
    normalized = normalize_severity_v2(raw_severity) if raw_severity else SEV3_MEDIUM
    labels: dict[str, Any] = dict(payload.get("labels") or {})
    annotations: dict[str, Any] = dict(payload.get("annotations") or {})
    fingerprint = str(payload.get("fingerprint") or "").strip() or None
    starts_at = _parse_dt(payload.get("starts_at"))
    ends_at = _parse_dt(payload.get("ends_at"))
    source_type = SOURCE_TYPE_SYNTHETIC if source == "synthetic_test" else SOURCE_TYPE_GENERIC
    return NormalizedAlert(
        source=source,
        source_type=source_type,
        alert_name=alert_name,
        severity=raw_severity or "unknown",
        normalized_severity=normalized,
        labels=labels,
        annotations=annotations,
        fingerprint=fingerprint,
        starts_at=starts_at,
        ends_at=ends_at,
        raw_status="firing",
    )


__all__ = [
    "NormalizedAlert",
    "SOURCE_TYPE_ALERTMANAGER",
    "SOURCE_TYPE_GENERIC",
    "SOURCE_TYPE_SYNTHETIC",
    "normalize_alertmanager_alert",
    "normalize_generic_alert",
]
