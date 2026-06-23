"""Step 54.1 -- application security & supply chain baseline (modeled, not enforced).

Read-only aggregation of the committed infra/security catalogs into a redacted
posture for the read-only operations API, /operations/safety, and the Admin
Console Security Posture view. NEVER runs a scanner, connects to a registry,
uploads source, writes to GitHub, pushes an image, or enables a production gate.
"""

from __future__ import annotations

from shared.sdk.security_foundation.collector import (
    LIMITATIONS,
    NEXT_REQUIRED_STEPS,
    STATUS_FAILED,
    STATUS_MODELED,
    STATUS_UNKNOWN,
    build_security_foundation_summary,
    collect_security_posture,
    load_security_foundation_summary,
)
from shared.sdk.security_foundation.report_builder import (
    foundation_view,
    full_report,
    load_summary,
    readiness_view,
    section,
)
from shared.sdk.security_foundation.safety import security_safety_fields

__all__ = [
    "LIMITATIONS",
    "NEXT_REQUIRED_STEPS",
    "STATUS_FAILED",
    "STATUS_MODELED",
    "STATUS_UNKNOWN",
    "build_security_foundation_summary",
    "collect_security_posture",
    "load_security_foundation_summary",
    "foundation_view",
    "full_report",
    "load_summary",
    "readiness_view",
    "section",
    "security_safety_fields",
]
