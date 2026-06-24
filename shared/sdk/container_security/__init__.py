"""Step 54.3 -- SBOM / image digest / container security baseline (modeled, locally verifiable).

Read-only loaders for the committed infra/security image/SBOM catalogs, container
safety fields for /operations/safety, and views for the read-only operations API.
NEVER logs into a registry, pulls/pushes an image, signs an image, generates an
attestation, uploads an SBOM, or enables a production gate. Local-only,
non-production.
"""

from __future__ import annotations

from shared.sdk.container_security.posture import (
    container_safety_fields,
    image_policy_view,
    load_runtime_report,
    readiness_view,
    sbom_status_view,
    section,
)

__all__ = [
    "container_safety_fields",
    "image_policy_view",
    "load_runtime_report",
    "readiness_view",
    "sbom_status_view",
    "section",
]
