"""Step 54.1 -- application security & supply chain foundation collector.

Read-only aggregation of the committed infra/security catalogs into a redacted
posture summary. Reads only repo YAML; never runs a scanner, connects to a
registry, uploads source, writes to GitHub, pushes an image, or enables a
production gate. A missing source yields status ``unknown`` (never a fake PASS).
A committed secret-shaped value, an enabled production gate, GitHub write, image
push, registry login, or external scanner upload flips status to ``failed``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from shared.sdk.secrets_foundation.secret_redaction import find_committed_secret

ROOT = Path(__file__).resolve().parents[3]

STATUS_MODELED = "modeled_not_enforced"
STATUS_FAILED = "failed"
STATUS_UNKNOWN = "unknown"

_SOURCES = (
    "application-security-asset-inventory.yaml",
    "supply-chain-inventory.yaml",
    "dependency-surface-inventory.yaml",
    "security-scan-policy-catalog.yaml",
    "sast-policy-model.yaml",
    "dependency-scan-policy-model.yaml",
    "secret-scan-policy-model.yaml",
    "sbom-policy-model.yaml",
    "container-image-security-policy.yaml",
    "threat-model-input-catalog.yaml",
    "release-risk-input-catalog.yaml",
    "security-evidence-model.yaml",
    "security-finding-taxonomy.yaml",
    "security-gate-fail-closed-policy.yaml",
)

LIMITATIONS = [
    "no_sast_toolchain_configured",
    "no_dependency_scan_toolchain_configured",
    "no_secret_scan_toolchain_configured",
    "no_sbom_generated",
    "no_image_vulnerability_scan",
    "python_dependencies_unpinned_no_lockfile",
    "container_images_not_digest_pinned",
    "dockerfiles_missing_nonroot_user",
    "no_threat_model_generated",
    "no_release_risk_summary",
    "no_production_security_gate",
]
NEXT_REQUIRED_STEPS = [
    "step_54_2_secret_scan_sast_dependency_scan_toolchain",
    "step_54_3_sbom_image_digest_container_security",
    "step_54_4_threat_model_release_risk_integrated_verification",
]


def _load(sdir: Path, name: str) -> dict[str, Any]:
    return yaml.safe_load((sdir / name).read_text(encoding="utf-8")) or {}


def collect_security_posture(root: Path | None = None) -> dict[str, Any]:
    base = root or ROOT
    sdir = base / "infra" / "security"

    missing = [s for s in _SOURCES if not (sdir / s).is_file()]
    if missing:
        return _unknown(missing)

    try:
        assets = _load(sdir, "application-security-asset-inventory.yaml")
        supply = _load(sdir, "supply-chain-inventory.yaml")["supplyChain"]
        sast = _load(sdir, "sast-policy-model.yaml")["sast"]
        depscan = _load(sdir, "dependency-scan-policy-model.yaml")["dependencyScan"]
        secretscan = _load(sdir, "secret-scan-policy-model.yaml")["secretScan"]
        sbom = _load(sdir, "sbom-policy-model.yaml")["sbom"]
        image = _load(sdir, "container-image-security-policy.yaml")["containerImageSecurity"]
        threat = _load(sdir, "threat-model-input-catalog.yaml")["threatModel"]
        release = _load(sdir, "release-risk-input-catalog.yaml")["releaseRisk"]
        evidence = _load(sdir, "security-evidence-model.yaml")["securityEvidence"]
        taxonomy = _load(sdir, "security-finding-taxonomy.yaml")
        gate = _load(sdir, "security-gate-fail-closed-policy.yaml")["gate"]
    except (KeyError, TypeError):
        return _unknown(["malformed_source"])

    asset_list = assets.get("assets", [])
    source_control = supply.get("sourceControl", {})
    containers = supply.get("containers", {})
    scanners = supply.get("scanners", {})
    py = supply.get("dependencies", {}).get("python", {})
    node = supply.get("dependencies", {}).get("node", {})

    # scan every committed security catalog for an inline secret value
    inline_hits: list[str] = []
    for p in sorted(sdir.glob("*.yaml")):
        inline_hits += find_committed_secret(p.read_text(encoding="utf-8"))

    posture: dict[str, Any] = {
        "productionReady": False,
        "sastConfigured": bool(sast.get("configured")),
        "dependencyScanConfigured": bool(depscan.get("configured")),
        "secretScanConfigured": bool(secretscan.get("configured")),
        "sbomConfigured": bool(sbom.get("configured")),
        "imageScanConfigured": bool(scanners.get("imageScanConfigured")),
        "imageDigestPolicyDefined": bool(
            image.get("requirements", {}).get("digestPinningRequired")
        ),
        "imageVulnerabilityPolicyDefined": bool(
            image.get("requirements", {}).get("imageVulnerabilityScanRequired")
        ),
        "threatModelRequired": bool(threat.get("required")),
        "releaseRiskSummaryRequired": bool(release.get("required")),
        "evidenceModelDefined": bool(evidence.get("evidenceTypes")),
        "findingTaxonomyDefined": bool(taxonomy.get("severities")),
        "gateFailClosedPolicyDefined": bool(gate.get("failClosed")),
        "assetInventoryPresent": bool(asset_list),
        "supplyChainInventoryPresent": True,
        "dependencySurfacePresent": (sdir / "dependency-surface-inventory.yaml").is_file(),
        "scanPolicyCatalogPresent": (sdir / "security-scan-policy-catalog.yaml").is_file(),
        "githubWriteEnabled": bool(source_control.get("writeEnabled")),
        "prCreationEnabled": bool(source_control.get("prCreationEnabled")),
        "imagePushEnabled": bool(supply.get("imagePush", {}).get("enabled")),
        "registryLoginEnabled": bool(supply.get("registryLogin", {}).get("enabled")),
        "externalScannerUploadEnabled": bool(
            supply.get("externalScannerUpload", {}).get("enabled")
        ),
        "productionGateEnabled": bool(gate.get("productionGateEnabled")),
        "imageDigestPinned": bool(containers.get("imageDigestPinned")),
        "pythonLockfilePresent": bool(py.get("lockFiles")),
        "nodeLockfilePresent": bool(node.get("lockFiles")),
        "committedSecretDetected": bool(inline_hits),
        "assetCount": len(asset_list),
        "productionRelevantAssetCount": sum(1 for a in asset_list if a.get("productionRelevant")),
        "dockerfileCount": int(containers.get("dockerfileCount", 0) or 0),
        "limitations": list(LIMITATIONS),
        "nextRequiredSteps": list(NEXT_REQUIRED_STEPS),
    }
    posture["status"] = _derive_status(posture)
    return posture


def _derive_status(p: dict[str, Any]) -> str:
    unsafe = (
        p["githubWriteEnabled"]
        or p["prCreationEnabled"]
        or p["imagePushEnabled"]
        or p["registryLoginEnabled"]
        or p["externalScannerUploadEnabled"]
        or p["productionGateEnabled"]
        or p["committedSecretDetected"]
        or p["productionReady"]
    )
    return STATUS_FAILED if unsafe else STATUS_MODELED


def _unknown(reasons: list[str]) -> dict[str, Any]:
    return {
        "status": STATUS_UNKNOWN,
        "productionReady": False,
        "sastConfigured": False,
        "dependencyScanConfigured": False,
        "secretScanConfigured": False,
        "sbomConfigured": False,
        "imageScanConfigured": False,
        "imageDigestPolicyDefined": False,
        "imageVulnerabilityPolicyDefined": False,
        "threatModelRequired": False,
        "releaseRiskSummaryRequired": False,
        "evidenceModelDefined": False,
        "findingTaxonomyDefined": False,
        "gateFailClosedPolicyDefined": False,
        "assetInventoryPresent": False,
        "supplyChainInventoryPresent": False,
        "githubWriteEnabled": False,
        "prCreationEnabled": False,
        "imagePushEnabled": False,
        "registryLoginEnabled": False,
        "externalScannerUploadEnabled": False,
        "committedSecretDetected": False,
        "limitations": ["security_foundation_source_missing"],
        "nextRequiredSteps": [],
        "missingSources": reasons,
    }


def build_security_foundation_summary(root: Path | None = None) -> dict[str, Any]:
    return {
        "version": "1",
        "meta": {"stage": "56A", "step": "54.1"},
        "securityFoundation": collect_security_posture(root),
    }


def load_security_foundation_summary(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    return data if isinstance(data, dict) else None


__all__ = [
    "STATUS_MODELED",
    "STATUS_FAILED",
    "STATUS_UNKNOWN",
    "LIMITATIONS",
    "NEXT_REQUIRED_STEPS",
    "collect_security_posture",
    "build_security_foundation_summary",
    "load_security_foundation_summary",
]
