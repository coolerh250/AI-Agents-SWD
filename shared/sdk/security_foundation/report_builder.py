"""Step 54.1 -- security foundation report builder (read-only, redacted).

Shapes the per-section views the read-only API serves, reading the committed
infra/security catalogs. Every view is passed through the Step 53 redaction so no
secret-shaped value can escape (none is expected -- the catalogs are metadata).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from shared.sdk.secrets_foundation.secret_redaction import redact
from shared.sdk.security_foundation.collector import (
    STATUS_UNKNOWN,
    load_security_foundation_summary,
)

ROOT = Path(__file__).resolve().parents[3]
_SUMMARY = ROOT / "infra" / "security" / "security-foundation-summary.yaml"


def _posture(summary: dict[str, Any] | None) -> dict[str, Any]:
    return (summary or {}).get("securityFoundation", {}) if summary else {}


def _catalog(name: str, root: Path | None = None) -> dict[str, Any]:
    p = (root or ROOT) / "infra" / "security" / name
    if not p.is_file():
        return {}
    return redact(yaml.safe_load(p.read_text(encoding="utf-8")) or {})


def foundation_view(summary: dict[str, Any] | None) -> dict[str, Any]:
    p = _posture(summary)
    return {
        "status": p.get("status", STATUS_UNKNOWN),
        "productionReady": False,
        "sastConfigured": bool(p.get("sastConfigured")),
        "dependencyScanConfigured": bool(p.get("dependencyScanConfigured")),
        "secretScanConfigured": bool(p.get("secretScanConfigured")),
        "sbomConfigured": bool(p.get("sbomConfigured")),
        "imageDigestPolicyDefined": bool(p.get("imageDigestPolicyDefined")),
        "imageVulnerabilityPolicyDefined": bool(p.get("imageVulnerabilityPolicyDefined")),
        "threatModelRequired": bool(p.get("threatModelRequired")),
        "releaseRiskSummaryRequired": bool(p.get("releaseRiskSummaryRequired")),
        "evidenceModelDefined": bool(p.get("evidenceModelDefined")),
        "findingTaxonomyDefined": bool(p.get("findingTaxonomyDefined")),
        "gateFailClosedPolicyDefined": bool(p.get("gateFailClosedPolicyDefined")),
        "githubWriteEnabled": bool(p.get("githubWriteEnabled")),
        "prCreationEnabled": bool(p.get("prCreationEnabled")),
        "imagePushEnabled": bool(p.get("imagePushEnabled")),
        "registryLoginEnabled": bool(p.get("registryLoginEnabled")),
        "externalScannerUploadEnabled": bool(p.get("externalScannerUploadEnabled")),
        "assetCount": int(p.get("assetCount", 0) or 0),
        "productionRelevantAssetCount": int(p.get("productionRelevantAssetCount", 0) or 0),
        "limitations": list(p.get("limitations", [])),
        "nextRequiredSteps": list(p.get("nextRequiredSteps", [])),
    }


def readiness_view(summary: dict[str, Any] | None) -> dict[str, Any]:
    p = _posture(summary)
    return {
        "status": p.get("status", STATUS_UNKNOWN),
        "productionReady": False,
        "productionGateEnabled": bool(p.get("productionGateEnabled")),
        "blockers": list(p.get("limitations", [])),
        "nextRequiredSteps": list(p.get("nextRequiredSteps", [])),
    }


def full_report(summary: dict[str, Any] | None, root: Path | None = None) -> dict[str, Any]:
    return {
        "status": _posture(summary).get("status", STATUS_UNKNOWN),
        "productionReady": False,
        "foundation": foundation_view(summary),
        "assets": _catalog("application-security-asset-inventory.yaml", root),
        "supplyChain": _catalog("supply-chain-inventory.yaml", root),
        "dependencies": _catalog("dependency-surface-inventory.yaml", root),
        "scanPolicies": _catalog("security-scan-policy-catalog.yaml", root),
        "sast": _catalog("sast-policy-model.yaml", root),
        "dependencyScan": _catalog("dependency-scan-policy-model.yaml", root),
        "secretScan": _catalog("secret-scan-policy-model.yaml", root),
        "sbom": _catalog("sbom-policy-model.yaml", root),
        "containerImages": _catalog("container-image-security-policy.yaml", root),
        "threatModel": _catalog("threat-model-input-catalog.yaml", root),
        "releaseRisk": _catalog("release-risk-input-catalog.yaml", root),
        "evidence": _catalog("security-evidence-model.yaml", root),
        "findingsTaxonomy": _catalog("security-finding-taxonomy.yaml", root),
        "gatePolicy": _catalog("security-gate-fail-closed-policy.yaml", root),
    }


def section(name: str, root: Path | None = None) -> dict[str, Any]:
    return _catalog(name, root)


def load_summary() -> dict[str, Any] | None:
    return load_security_foundation_summary(_SUMMARY)


__all__ = [
    "foundation_view",
    "readiness_view",
    "full_report",
    "section",
    "load_summary",
]
