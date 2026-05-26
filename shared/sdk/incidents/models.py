from dataclasses import dataclass, field
from typing import Any

INCIDENT_SEVERITIES = ("sev1", "sev2", "sev3", "sev4")
INCIDENT_STATUSES = ("open", "acknowledged", "resolved")


def normalize_severity(value: str | None) -> str:
    """Coerce a free-form severity string to one of the canonical SEV values."""
    if not value:
        return "sev3"
    lowered = str(value).strip().lower()
    return lowered if lowered in INCIDENT_SEVERITIES else "sev3"


def normalize_status(value: str | None) -> str:
    """Coerce a free-form status string to one of the canonical lifecycle values."""
    if not value:
        return "open"
    lowered = str(value).strip().lower()
    return lowered if lowered in INCIDENT_STATUSES else "open"


@dataclass
class Incident:
    """In-memory representation of one ``incident_records`` row.

    ``incident_id`` is the operator-facing UUID. ``task_id`` / ``workflow_id``
    are nullable because operator-created incidents need not be tied to a
    workflow. ``details`` is the JSONB payload (original event, failure
    reason, retry counts).
    """

    incident_id: str
    severity: str
    status: str
    source: str
    summary: str
    task_id: str | None = None
    workflow_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    acknowledged_at: str | None = None
    resolved_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "task_id": self.task_id,
            "workflow_id": self.workflow_id,
            "severity": self.severity,
            "status": self.status,
            "source": self.source,
            "summary": self.summary,
            "details": dict(self.details),
            "acknowledged_at": self.acknowledged_at,
            "resolved_at": self.resolved_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
