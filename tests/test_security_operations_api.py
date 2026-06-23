"""Step 54.1 -- security operations API surface (router introspection)."""

from __future__ import annotations

import security_posture_api as sp

EXPECTED_PATHS = {
    "/operations/security/foundation",
    "/operations/security/assets",
    "/operations/security/supply-chain",
    "/operations/security/dependencies",
    "/operations/security/scan-policies",
    "/operations/security/sast",
    "/operations/security/dependency-scan",
    "/operations/security/secret-scan",
    "/operations/security/sbom",
    "/operations/security/container-images",
    "/operations/security/threat-model",
    "/operations/security/release-risk",
    "/operations/security/evidence",
    "/operations/security/findings-taxonomy",
    "/operations/security/gate-policy",
    "/operations/security/readiness",
    "/operations/security/report",
}


def test_expected_endpoints_present() -> None:
    paths = {getattr(r, "path", "") for r in sp.router.routes}
    assert EXPECTED_PATHS <= paths


def test_foundation_view_is_not_production_ready() -> None:
    from pathlib import Path

    from shared.sdk.security_foundation import (
        foundation_view,
        load_security_foundation_summary,
    )

    root = Path(__file__).resolve().parents[1]
    summary = load_security_foundation_summary(
        root / "infra" / "security" / "security-foundation-summary.yaml"
    )
    view = foundation_view(summary)
    assert view["productionReady"] is False
    assert view["status"] in ("modeled_not_enforced", "unknown")


def test_report_has_all_sections() -> None:
    from pathlib import Path

    from shared.sdk.security_foundation import full_report, load_security_foundation_summary

    root = Path(__file__).resolve().parents[1]
    summary = load_security_foundation_summary(
        root / "infra" / "security" / "security-foundation-summary.yaml"
    )
    rep = full_report(summary, root=root)
    for section in (
        "assets",
        "supplyChain",
        "dependencies",
        "scanPolicies",
        "sast",
        "dependencyScan",
        "secretScan",
        "sbom",
        "containerImages",
        "threatModel",
        "releaseRisk",
        "evidence",
        "findingsTaxonomy",
        "gatePolicy",
    ):
        assert section in rep
    assert rep["productionReady"] is False
