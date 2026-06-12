"""Stage 40 -- SEV severity constants and mapping helpers."""

from __future__ import annotations

SEV1_CRITICAL = "SEV1_CRITICAL"
SEV2_HIGH = "SEV2_HIGH"
SEV3_MEDIUM = "SEV3_MEDIUM"
SEV4_LOW = "SEV4_LOW"
SEV5_INFO = "SEV5_INFO"

ALL_SEVERITIES = (SEV1_CRITICAL, SEV2_HIGH, SEV3_MEDIUM, SEV4_LOW, SEV5_INFO)

# Legacy short-form used by incident_records.severity before Stage 40.
_LEGACY_MAP: dict[str, str] = {
    "sev1": SEV1_CRITICAL,
    "sev2": SEV2_HIGH,
    "sev3": SEV3_MEDIUM,
    "sev4": SEV4_LOW,
    "sev5": SEV5_INFO,
    "critical": SEV1_CRITICAL,
    "high": SEV2_HIGH,
    "warning": SEV3_MEDIUM,
    "medium": SEV3_MEDIUM,
    "low": SEV4_LOW,
    "info": SEV5_INFO,
    "informational": SEV5_INFO,
}


def normalize_severity_v2(value: str | None) -> str:
    """Coerce any severity string to a canonical SEV* constant."""
    if not value:
        return SEV4_LOW
    candidate = str(value).strip()
    if candidate in ALL_SEVERITIES:
        return candidate
    return _LEGACY_MAP.get(candidate.lower(), SEV4_LOW)


def postmortem_required(severity: str) -> bool:
    """SEV1 and SEV2 always require a postmortem."""
    return severity in (SEV1_CRITICAL, SEV2_HIGH)


__all__ = [
    "SEV1_CRITICAL",
    "SEV2_HIGH",
    "SEV3_MEDIUM",
    "SEV4_LOW",
    "SEV5_INFO",
    "ALL_SEVERITIES",
    "normalize_severity_v2",
    "postmortem_required",
]
