"""Step 54.1 -- read-only application security & supply chain foundation API.

GET-only visibility over the COMMITTED infra/security catalogs. NO write
endpoints, NO run-scan / connect-scanner / upload-source / configure-scanner
endpoint, NO GitHub write, NO image push, NO registry login, NO production gate
toggle, NO user-provided path. Every response is passed through redaction. Absent
summary -> ``status: unknown`` (never a fake PASS).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter

from shared.sdk.security_foundation import (
    foundation_view,
    full_report,
    load_security_foundation_summary,
    readiness_view,
    section,
)
from shared.sdk.security_findings import scan_posture
from shared.sdk.container_security import posture as container_posture
from shared.sdk.security_integrated import posture as integrated_posture

router = APIRouter(prefix="/operations/security", tags=["security-foundation"])

_SUMMARY_PATH = Path("infra/security/security-foundation-summary.yaml")


def _summary() -> dict[str, Any] | None:
    return load_security_foundation_summary(_SUMMARY_PATH)


@router.get("/foundation")
def security_foundation() -> dict:
    return foundation_view(_summary())


@router.get("/assets")
def security_assets() -> dict:
    return section("application-security-asset-inventory.yaml")


@router.get("/supply-chain")
def security_supply_chain() -> dict:
    return section("supply-chain-inventory.yaml")


@router.get("/dependencies")
def security_dependencies() -> dict:
    return section("dependency-surface-inventory.yaml")


@router.get("/scan-policies")
def security_scan_policies() -> dict:
    return section("security-scan-policy-catalog.yaml")


@router.get("/sast")
def security_sast() -> dict:
    return section("sast-policy-model.yaml")


@router.get("/dependency-scan")
def security_dependency_scan() -> dict:
    return section("dependency-scan-policy-model.yaml")


@router.get("/secret-scan")
def security_secret_scan() -> dict:
    return section("secret-scan-policy-model.yaml")


@router.get("/sbom")
def security_sbom() -> dict:
    return section("sbom-policy-model.yaml")


@router.get("/container-images")
def security_container_images() -> dict:
    return section("container-image-security-policy.yaml")


@router.get("/threat-model")
def security_threat_model() -> dict:
    return section("threat-model-input-catalog.yaml")


@router.get("/release-risk")
def security_release_risk() -> dict:
    return section("release-risk-input-catalog.yaml")


@router.get("/evidence")
def security_evidence() -> dict:
    return section("security-evidence-model.yaml")


@router.get("/findings-taxonomy")
def security_findings_taxonomy() -> dict:
    return section("security-finding-taxonomy.yaml")


@router.get("/gate-policy")
def security_gate_policy() -> dict:
    return section("security-gate-fail-closed-policy.yaml")


@router.get("/readiness")
def security_readiness() -> dict:
    return readiness_view(_summary())


@router.get("/report")
def security_report() -> dict:
    return full_report(_summary())


# ---------------------------------------------------------------------------
# Step 54.2 -- read-only local scan toolchain posture. GET-only. NO run-scan /
# upload / connect / configure endpoint. Runtime scan reports are NEVER committed
# and are absent in the image, so live views degrade to not_run -- never clean.
# ---------------------------------------------------------------------------


@router.get("/scans/status")
def security_scans_status() -> dict:
    return scan_posture.status_view()


@router.get("/scans/capabilities")
def security_scans_capabilities() -> dict:
    return scan_posture.section("local-scanner-capability-inventory.yaml")


@router.get("/scans/targets")
def security_scans_targets() -> dict:
    return scan_posture.section("scan-target-catalog.yaml")


@router.get("/scans/exclusions")
def security_scans_exclusions() -> dict:
    return scan_posture.section("scan-exclusion-policy.yaml")


@router.get("/scans/secret")
def security_scans_secret() -> dict:
    return scan_posture.scan_section("secret")


@router.get("/scans/sast")
def security_scans_sast() -> dict:
    return scan_posture.scan_section("sast")


@router.get("/scans/dependencies")
def security_scans_dependencies() -> dict:
    return scan_posture.scan_section("dependency")


@router.get("/scans/summary")
def security_scans_summary() -> dict:
    return scan_posture.summary_view()


@router.get("/scans/readiness")
def security_scans_readiness() -> dict:
    return scan_posture.readiness_view()


# ---------------------------------------------------------------------------
# Step 54.3 -- read-only SBOM / container security posture. GET-only. NO
# generate-SBOM / scan-image / registry-login / image-push / sign / attest
# endpoint, NO arbitrary image ref / path. Runtime SBOM + image-policy reports are
# NEVER committed and absent in the image, so live views degrade to not_run.
# ---------------------------------------------------------------------------


@router.get("/sbom/status")
def security_sbom_status() -> dict:
    return container_posture.sbom_status_view()


@router.get("/sbom/capabilities")
def security_sbom_capabilities() -> dict:
    return container_posture.section("sbom-capability-inventory.yaml")


@router.get("/sbom/report")
def security_sbom_report() -> dict:
    return container_posture.sbom_status_view()


@router.get("/images/inventory")
def security_images_inventory() -> dict:
    return container_posture.section("container-image-inventory.yaml")


@router.get("/images/digest-policy")
def security_images_digest_policy() -> dict:
    return container_posture.section("image-digest-policy.yaml")


@router.get("/images/tag-policy")
def security_images_tag_policy() -> dict:
    return container_posture.section("image-tag-policy.yaml")


@router.get("/images/dockerfiles")
def security_images_dockerfiles() -> dict:
    return container_posture.section("dockerfile-security-inventory.yaml")


@router.get("/images/runtime-alignment")
def security_images_runtime_alignment() -> dict:
    return container_posture.section("container-runtime-security-alignment.yaml")


@router.get("/images/vulnerability-capability")
def security_images_vulnerability_capability() -> dict:
    return container_posture.section("image-vulnerability-scan-capability.yaml")


@router.get("/images/policy-report")
def security_images_policy_report() -> dict:
    return container_posture.image_policy_view()


@router.get("/images/signing-attestation")
def security_images_signing_attestation() -> dict:
    return container_posture.section("image-signing-attestation-model.yaml")


@router.get("/images/registry-boundary")
def security_images_registry_boundary() -> dict:
    return container_posture.section("registry-credential-boundary.yaml")


@router.get("/images/readiness")
def security_images_readiness() -> dict:
    return container_posture.readiness_view()


# ---------------------------------------------------------------------------
# Step 54.4 -- read-only integrated security posture (threat model / release risk
# / evidence package / readiness). GET-only. NO generate-evidence, NO
# approve-release, NO production-gate, NO deploy endpoint, NO arbitrary path.
# Runtime evidence/risk/readiness artifacts are NEVER committed and are absent in
# the image, so those live views degrade to not_run -- never a fake approval.
# ---------------------------------------------------------------------------


@router.get("/threat-model/baseline")
def security_threat_model_baseline() -> dict:
    return integrated_posture.section("threat-model-baseline.yaml")


@router.get("/threat-model/agent")
def security_threat_model_agent() -> dict:
    return integrated_posture.section("agent-threat-model.yaml")


@router.get("/threat-model/supply-chain")
def security_threat_model_supply_chain() -> dict:
    return integrated_posture.section("supply-chain-threat-model.yaml")


@router.get("/threat-model/runtime-gitops")
def security_threat_model_runtime_gitops() -> dict:
    return integrated_posture.section("runtime-gitops-threat-model.yaml")


@router.get("/release-risk/model")
def security_release_risk_model() -> dict:
    return integrated_posture.section("release-risk-summary-model.yaml")


@router.get("/release-risk/summary")
def security_release_risk_summary() -> dict:
    return integrated_posture.release_risk_summary_view()


@router.get("/evidence/package")
def security_evidence_package() -> dict:
    return integrated_posture.evidence_package_view()


@router.get("/readiness/report")
def security_readiness_report() -> dict:
    return integrated_posture.readiness_report_view()


@router.get("/step54/status")
def security_step54_status() -> dict:
    return integrated_posture.step54_status_view()


__all__ = ["router"]
