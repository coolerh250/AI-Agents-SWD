"""Step 54.2 -- normalized security finding + scan result models.

A ``SecurityFinding`` never stores a secret value: ``evidence_redacted`` is passed
through redaction and ``finding_id`` is a deterministic hash of
scanner/category/rule/path/line. ``ScanResult`` carries the per-run summary; a
tool-unavailable run is never ``passed`` and a run with findings is never clean.
"""

from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from shared.sdk.security_findings.redaction import redact_evidence

Category = Literal["secret", "sast", "dependency"]
Severity = Literal["critical", "high", "medium", "low", "informational"]
ScanStatus = Literal[
    "passed",
    "completed_with_findings",
    "tool_unavailable",
    "config_error",
    "failed",
]

SECRET_SHAPE_TOKENS = ("token", "secret", "password", "private", "key", "credential")


class SecurityFinding(BaseModel, extra="forbid"):
    finding_id: str
    scanner: str
    category: Category
    severity: Severity
    title: str
    description: str = ""
    file_path: str | None = None
    line: int | None = None
    rule_id: str | None = None
    evidence_redacted: str | None = None
    remediation: str | None = None
    production_blocker: bool = False
    requires_approval: bool = False

    @field_validator("evidence_redacted")
    @classmethod
    def _redact(cls, v: str | None) -> str | None:
        return redact_evidence(v)

    @field_validator("file_path")
    @classmethod
    def _no_abs_or_traversal(cls, v: str | None) -> str | None:
        if v is None:
            return None
        norm = v.replace("\\", "/")
        if norm.startswith("/") or ".." in norm.split("/") or (len(norm) > 1 and norm[1] == ":"):
            raise ValueError(f"file_path must be a repo-relative path, got {v!r}")
        return norm


def make_finding_id(
    scanner: str, category: str, rule_id: str | None, path: str | None, line: int | None
) -> str:
    raw = f"{scanner}|{category}|{rule_id or ''}|{path or ''}|{line if line is not None else ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def severity_flags(category: str, severity: str) -> tuple[bool, bool]:
    """Return (production_blocker, requires_approval) from category+severity."""
    if category == "secret":
        return True, False  # any confirmed secret finding is a production blocker
    if severity == "critical":
        return True, False
    if severity == "high":
        return True, True  # fail or explicit approval
    if severity == "medium":
        return False, True
    return False, False


class FindingsSummary(BaseModel, extra="forbid"):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    informational: int = 0

    @classmethod
    def from_findings(cls, findings: list[SecurityFinding]) -> "FindingsSummary":
        s = cls()
        for f in findings:
            setattr(s, f.severity, getattr(s, f.severity) + 1)
        return s


class ScanResult(BaseModel, extra="forbid"):
    schema_version: str = "1"
    scan_type: Category
    scanner: str
    local_only: bool = True
    network_used: bool = False
    source_uploaded: bool = False
    token_used: bool = False
    started_at: str = ""
    finished_at: str = ""
    status: ScanStatus
    targets: list[str] = Field(default_factory=list)
    excluded_targets: list[str] = Field(default_factory=list)
    findings_summary: FindingsSummary = Field(default_factory=FindingsSummary)
    findings: list[SecurityFinding] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    production_ready: bool = False

    @field_validator("production_ready")
    @classmethod
    def _never_production_ready(cls, v: bool) -> bool:
        return False


__all__ = [
    "Category",
    "Severity",
    "ScanStatus",
    "SecurityFinding",
    "FindingsSummary",
    "ScanResult",
    "make_finding_id",
    "severity_flags",
]
