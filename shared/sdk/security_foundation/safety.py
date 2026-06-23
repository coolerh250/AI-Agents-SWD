"""Step 54.1 -- flat /operations/safety security & supply-chain fields.

Booleans / enums only. Absent summary -> safe `unknown` posture;
``security_production_ready`` is ALWAYS false. ``production_executed_true_count``
is NOT emitted here -- it is owned by the DB-based production-safety summary.
"""

from __future__ import annotations

from typing import Any

STATUS_UNKNOWN = "unknown"


def security_safety_fields(summary: dict[str, Any] | None) -> dict[str, Any]:
    p = (summary or {}).get("securityFoundation", {}) if summary else {}
    status = p.get("status", STATUS_UNKNOWN)
    return {
        "security_foundation_enabled": True,
        "security_foundation_status": status,
        "security_sast_configured": bool(p.get("sastConfigured")),
        "security_dependency_scan_configured": bool(p.get("dependencyScanConfigured")),
        "security_secret_scan_configured": bool(p.get("secretScanConfigured")),
        "security_sbom_configured": bool(p.get("sbomConfigured")),
        "security_image_digest_policy_defined": bool(p.get("imageDigestPolicyDefined")),
        "security_image_vulnerability_policy_defined": bool(
            p.get("imageVulnerabilityPolicyDefined")
        ),
        "security_threat_model_required": bool(p.get("threatModelRequired")),
        "security_release_risk_summary_required": bool(p.get("releaseRiskSummaryRequired")),
        "security_evidence_model_defined": bool(p.get("evidenceModelDefined")),
        "security_finding_taxonomy_defined": bool(p.get("findingTaxonomyDefined")),
        "security_gate_fail_closed_policy_defined": bool(p.get("gateFailClosedPolicyDefined")),
        "security_production_ready": False,
        "supply_chain_inventory_present": bool(p.get("supplyChainInventoryPresent")),
        "supply_chain_github_write_enabled": bool(p.get("githubWriteEnabled")),
        "supply_chain_pr_creation_enabled": bool(p.get("prCreationEnabled")),
        "supply_chain_image_push_enabled": bool(p.get("imagePushEnabled")),
        "supply_chain_registry_login_enabled": bool(p.get("registryLoginEnabled")),
        "supply_chain_external_scanner_upload_enabled": bool(p.get("externalScannerUploadEnabled")),
    }


__all__ = ["security_safety_fields"]
