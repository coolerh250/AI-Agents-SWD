"""Step 52.4 -- read-only identity posture aggregation (no network, no secrets).

Aggregates the COMMITTED Step 52.1/52.2/52.3 identity models into a redacted
posture summary for the read-only operations API, /operations/safety, and the
Admin Console identity view. NEVER connects to an IdP, fetches discovery/JWKS,
reads a secret, runs a verifier, or enables production auth.
"""

from __future__ import annotations

from shared.sdk.identity_posture.collector import (
    LIMITATIONS,
    NEXT_REQUIRED_STEPS,
    build_identity_posture_summary,
    collect_identity_posture,
    load_identity_posture_summary,
)
from shared.sdk.identity_posture.models import (
    POSTURE_STATUSES,
    STATUS_FAILED,
    STATUS_MODELED,
    STATUS_UNKNOWN,
)
from shared.sdk.identity_posture.redaction import find_sensitive, is_redacted
from shared.sdk.identity_posture.report_builder import (
    full_report,
    posture_view,
    readiness_view,
    section_view,
)
from shared.sdk.identity_posture.safety import identity_posture_safety_fields

__all__ = [
    "LIMITATIONS",
    "NEXT_REQUIRED_STEPS",
    "build_identity_posture_summary",
    "collect_identity_posture",
    "load_identity_posture_summary",
    "POSTURE_STATUSES",
    "STATUS_FAILED",
    "STATUS_MODELED",
    "STATUS_UNKNOWN",
    "find_sensitive",
    "is_redacted",
    "full_report",
    "posture_view",
    "readiness_view",
    "section_view",
    "identity_posture_safety_fields",
]
