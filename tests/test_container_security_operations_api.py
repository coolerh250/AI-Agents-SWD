"""Step 54.3 -- SBOM / container security operations API surface."""

from __future__ import annotations

import security_posture_api as sp

EXPECTED = {
    "/operations/security/sbom/status",
    "/operations/security/sbom/capabilities",
    "/operations/security/sbom/report",
    "/operations/security/images/inventory",
    "/operations/security/images/digest-policy",
    "/operations/security/images/tag-policy",
    "/operations/security/images/dockerfiles",
    "/operations/security/images/runtime-alignment",
    "/operations/security/images/vulnerability-capability",
    "/operations/security/images/policy-report",
    "/operations/security/images/signing-attestation",
    "/operations/security/images/registry-boundary",
    "/operations/security/images/readiness",
}


def test_expected_endpoints_present() -> None:
    paths = {getattr(r, "path", "") for r in sp.router.routes}
    assert EXPECTED <= paths


def test_sbom_status_view_not_production_ready() -> None:
    from shared.sdk.container_security import sbom_status_view

    v = sbom_status_view()
    assert v["productionReady"] is False
    assert "baselineEnabled" in v


def test_image_readiness_not_ready() -> None:
    from shared.sdk.container_security import readiness_view

    v = readiness_view()
    assert v["productionReady"] is False
    assert v["productionGateEnabled"] is False
    assert v["blockers"]
