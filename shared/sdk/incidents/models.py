from dataclasses import dataclass, field
from typing import Any

INCIDENT_SEVERITIES = ("sev1", "sev2", "sev3", "sev4")
# Stage 40: extended statuses
INCIDENT_STATUSES = (
    "open",
    "acknowledged",
    "investigating",
    "mitigated",
    "resolved",
    "closed",
    "reopened",
    "suppressed",
)


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
    """In-memory representation of one ``incident_records`` row."""

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
    closed_at: str | None = None
    normalized_severity: str | None = None
    postmortem_required: bool = False
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "task_id": self.task_id,
            "workflow_id": self.workflow_id,
            "severity": self.severity,
            "normalized_severity": self.normalized_severity,
            "status": self.status,
            "source": self.source,
            "summary": self.summary,
            "details": dict(self.details),
            "postmortem_required": self.postmortem_required,
            "acknowledged_at": self.acknowledged_at,
            "resolved_at": self.resolved_at,
            "closed_at": self.closed_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
