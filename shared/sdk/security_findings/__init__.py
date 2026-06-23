"""Step 54.2 -- local security scan toolchain baseline (modeled, locally executable).

Normalized finding + scan-result models, redaction, a result normalizer, and
read-only scan posture loaders. NEVER uploads source, contacts an external
scanner, uses a token, writes to GitHub, pushes an image, or enables a production
gate. Local-only, non-production.
"""

from __future__ import annotations

from shared.sdk.security_findings.models import (
    Category,
    FindingsSummary,
    ScanResult,
    ScanStatus,
    SecurityFinding,
    Severity,
    make_finding_id,
    severity_flags,
)
from shared.sdk.security_findings.normalizer import SCAN_TYPES, normalize
from shared.sdk.security_findings.redaction import (
    REDACTION_TOKEN,
    redact_evidence,
    redact_report,
)
from shared.sdk.security_findings.scan_posture import (
    load_runtime_summary,
    load_status_model,
    readiness_view,
    scan_safety_fields,
    scan_section,
    section,
    status_view,
    summary_view,
)

__all__ = [
    "Category",
    "Severity",
    "ScanStatus",
    "SecurityFinding",
    "FindingsSummary",
    "ScanResult",
    "make_finding_id",
    "severity_flags",
    "normalize",
    "SCAN_TYPES",
    "REDACTION_TOKEN",
    "redact_evidence",
    "redact_report",
    "load_runtime_summary",
    "load_status_model",
    "readiness_view",
    "scan_safety_fields",
    "scan_section",
    "section",
    "status_view",
    "summary_view",
]
