"""Step 54.3 -- read-only SBOM / container security posture loaders + safety fields.

Reads the COMMITTED infra/security image/SBOM catalogs and (optionally) the latest
redacted runtime reports under ``.runtime/security/``. Runtime reports are NEVER
committed and are absent in the orchestrator image, so live SBOM / image-policy
views degrade to ``not_run`` -- never a fake clean/PASS. No image is pulled, no
registry is contacted, no scan is run here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from shared.sdk.secrets_foundation.secret_redaction import redact

ROOT = Path(__file__).resolve().parents[3]

_CATALOGS = {
    "sbom_capability": "sbom-capability-inventory.yaml",
    "sbom_boundary": "sbom-generation-boundary.yaml",
    "sbom_schema": "sbom-artifact-schema.yaml",
    "image_inventory": "container-image-inventory.yaml",
    "digest_policy": "image-digest-policy.yaml",
    "tag_policy": "image-tag-policy.yaml",
    "dockerfile_inventory": "dockerfile-security-inventory.yaml",
    "runtime_alignment": "container-runtime-security-alignment.yaml",
    "vuln_capability": "image-vulnerability-scan-capability.yaml",
    "vuln_schema": "image-vulnerability-result-schema.yaml",
    "signing": "image-signing-attestation-model.yaml",
    "registry_boundary": "registry-credential-boundary.yaml",
    "evidence": "container-security-evidence-model.yaml",
}


def _load_yaml(name: str, root: Path | None = None) -> dict[str, Any]:
    p = (root or ROOT) / "infra" / "security" / name
    if not p.is_file():
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def section(name: str, root: Path | None = None) -> dict[str, Any]:
    return redact(_load_yaml(name, root))


def load_runtime_report(name: str, runtime_dir: Path | None = None) -> dict[str, Any] | None:
    base = runtime_dir or (ROOT / ".runtime" / "security")
    p = base / name
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return redact(data) if isinstance(data, dict) else None


def container_safety_fields(root: Path | None = None) -> dict[str, Any]:
    base = root or ROOT
    sbom_cap = _load_yaml(_CATALOGS["sbom_capability"], base)
    sbom_bound = _load_yaml(_CATALOGS["sbom_boundary"], base).get("sbomGeneration", {})
    inv = _load_yaml(_CATALOGS["image_inventory"], base)
    digest = _load_yaml(_CATALOGS["digest_policy"], base).get("imageDigestPolicy", {})
    dockerfiles = _load_yaml(_CATALOGS["dockerfile_inventory"], base).get("dockerfiles", [])
    align = _load_yaml(_CATALOGS["runtime_alignment"], base).get("runtimeAlignment", {})
    vuln = _load_yaml(_CATALOGS["vuln_capability"], base)
    signing = _load_yaml(_CATALOGS["signing"], base).get("signingAttestation", {})
    registry = _load_yaml(_CATALOGS["registry_boundary"], base).get(
        "registryCredentialBoundary", {}
    )

    images = inv.get("images", [])
    sbom_configured = any(t.get("configured") for t in sbom_cap.get("sbomTools", []))
    digest_complete = bool(digest.get("currentState", {}).get("anyDigestPinned"))
    latest_detected = any(img.get("latestTag") for img in images)
    non_root_complete = bool(dockerfiles) and all(d.get("hasUserInstruction") for d in dockerfiles)
    policy_findings_present = any(img.get("blockers") for img in images)
    vuln_configured = (
        "limited_policy_baseline"
        if any(s.get("configured") for s in vuln.get("scanners", []))
        else False
    )

    return {
        "security_sbom_baseline_enabled": sbom_configured,
        "security_sbom_generation_local_only": bool(sbom_bound.get("localOnly")),
        "security_sbom_external_upload_enabled": bool(sbom_bound.get("externalUploadAllowed")),
        "security_sbom_runtime_reports_committed": bool(
            sbom_bound.get("committedRuntimeReportsAllowed")
        ),
        "security_sbom_production_ready": False,
        "security_container_image_inventory_present": bool(images),
        "security_image_digest_policy_defined": bool(digest.get("digestRequired")),
        "security_image_digest_pinning_complete": digest_complete,
        "security_latest_tag_detected": latest_detected,
        "security_dockerfile_security_inventory_present": bool(dockerfiles),
        "security_dockerfile_non_root_complete": non_root_complete,
        "security_container_runtime_alignment_present": bool(align),
        "security_image_vulnerability_scan_configured": vuln_configured,
        "security_image_vulnerability_cve_scan_performed": bool(vuln.get("cveScanPerformed")),
        "security_image_policy_scan_enabled": True,
        "security_image_policy_findings_present": policy_findings_present,
        "security_image_signing_configured": bool(signing.get("signingConfigured")),
        "security_image_attestation_configured": bool(signing.get("attestationConfigured")),
        "security_registry_login_enabled": bool(registry.get("registryLoginInThisStage")),
        "security_image_push_enabled": bool(registry.get("imagePushInThisStage")),
        "security_container_production_ready": False,
    }


def sbom_status_view(root: Path | None = None, runtime_dir: Path | None = None) -> dict[str, Any]:
    cap = _load_yaml(_CATALOGS["sbom_capability"], root)
    bound = _load_yaml(_CATALOGS["sbom_boundary"], root).get("sbomGeneration", {})
    report = load_runtime_report("sbom/local-sbom-baseline.json", runtime_dir)
    return {
        "baselineEnabled": any(t.get("configured") for t in cap.get("sbomTools", [])),
        "localOnly": bool(bound.get("localOnly")),
        "externalUploadEnabled": bool(bound.get("externalUploadAllowed")),
        "runtimeReportsCommitted": bool(bound.get("committedRuntimeReportsAllowed")),
        "latest": report or {"status": "not_run"},
        "productionReady": False,
    }


def image_policy_view(runtime_dir: Path | None = None) -> dict[str, Any]:
    report = load_runtime_report("images/image-policy-report.json", runtime_dir)
    if report is None:
        return {"status": "not_run", "productionReady": False}
    report["productionReady"] = False
    return report


def readiness_view(root: Path | None = None) -> dict[str, Any]:
    fields = container_safety_fields(root)
    blockers: list[str] = []
    if not fields["security_image_digest_pinning_complete"]:
        blockers.append("image_digest_pinning_incomplete")
    if not fields["security_dockerfile_non_root_complete"]:
        blockers.append("dockerfiles_not_non_root")
    if not fields["security_image_vulnerability_cve_scan_performed"]:
        blockers.append("image_cve_scan_not_performed")
    if not fields["security_image_signing_configured"]:
        blockers.append("image_signing_not_configured")
    blockers.append("non_production_cluster_smoke_required_step_55")
    return {
        "status": "modeled_locally_verifiable",
        "productionReady": False,
        "productionGateEnabled": False,
        "blockers": blockers,
    }


__all__ = [
    "section",
    "load_runtime_report",
    "container_safety_fields",
    "sbom_status_view",
    "image_policy_view",
    "readiness_view",
]
