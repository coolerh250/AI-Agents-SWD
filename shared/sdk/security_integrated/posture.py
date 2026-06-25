"""Step 54.4 -- read-only integrated security posture (threat model / release risk
/ evidence package / readiness).

Reads the COMMITTED infra/security threat-model, release-risk and evidence-schema
catalogs and (optionally) the latest redacted runtime artifacts under
``.runtime/security/``. Runtime artifacts (evidence package, release risk summary,
readiness report) are NEVER committed and are absent in the orchestrator image, so
the live views degrade to ``not_run`` -- never a fake clean/PASS/approval. Nothing
here uploads, connects to a scanner, writes to GitHub, enables a gate, or approves
a release.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from shared.sdk.secrets_foundation.secret_redaction import redact

ROOT = Path(__file__).resolve().parents[3]

_PRESENT_FILES = {
    "threat_model": "threat-model-baseline.yaml",
    "agent_threat_model": "agent-threat-model.yaml",
    "supply_chain_threat_model": "supply-chain-threat-model.yaml",
    "runtime_gitops_threat_model": "runtime-gitops-threat-model.yaml",
    "release_risk_summary_model": "release-risk-summary-model.yaml",
    "evidence_package_schema": "security-evidence-package-schema.yaml",
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


def integrated_safety_fields(root: Path | None = None) -> dict[str, Any]:
    base = root or ROOT
    summ = _load_yaml("security-integrated-summary.yaml", base).get("securityIntegrated", {})

    def present(name: str) -> bool:
        return (base / "infra" / "security" / name).is_file()

    return {
        "security_threat_model_present": present(_PRESENT_FILES["threat_model"]),
        "security_agent_threat_model_present": present(_PRESENT_FILES["agent_threat_model"]),
        "security_supply_chain_threat_model_present": present(
            _PRESENT_FILES["supply_chain_threat_model"]
        ),
        "security_runtime_gitops_threat_model_present": present(
            _PRESENT_FILES["runtime_gitops_threat_model"]
        ),
        "security_release_risk_summary_model_present": present(
            _PRESENT_FILES["release_risk_summary_model"]
        ),
        "security_release_risk_summary_generated": bool(summ.get("releaseRiskSummaryGenerated")),
        "security_evidence_package_schema_present": present(
            _PRESENT_FILES["evidence_package_schema"]
        ),
        "security_evidence_package_generated": bool(summ.get("evidencePackageGenerated")),
        "security_readiness_report_generated": bool(summ.get("readinessReportGenerated")),
        "security_missing_evidence_blocks_production": bool(
            summ.get("missingEvidenceBlocksProduction")
        ),
        "security_critical_finding_blocks_production": bool(
            summ.get("criticalFindingBlocksProduction")
        ),
        "security_release_gate_enabled": bool(summ.get("releaseGateEnabled")),
        "security_step54_integrated": bool(summ.get("step54Integrated")),
        "security_step54_production_ready": False,
    }


def evidence_package_view(runtime_dir: Path | None = None) -> dict[str, Any]:
    report = load_runtime_report("security-evidence-package.json", runtime_dir)
    if report is None:
        return {"status": "not_run", "productionReady": False}
    report["productionReady"] = False
    return report


def release_risk_summary_view(runtime_dir: Path | None = None) -> dict[str, Any]:
    report = load_runtime_report("release-risk-summary.json", runtime_dir)
    if report is None:
        return {"status": "not_run", "productionReady": False}
    report["productionReady"] = False
    return report


def readiness_report_view(runtime_dir: Path | None = None) -> dict[str, Any]:
    report = load_runtime_report("security-readiness-report.json", runtime_dir)
    if report is None:
        return {"status": "not_run", "productionReady": False}
    report["productionReady"] = False
    return report


def step54_status_view(root: Path | None = None) -> dict[str, Any]:
    fields = integrated_safety_fields(root)
    tm = _load_yaml(_PRESENT_FILES["threat_model"], root).get("threatModel", {})
    blockers = list(tm.get("blockers", []))
    return {
        "status": "modeled_locally_verifiable_not_production_enforced",
        "productionReady": False,
        "releaseGateEnabled": False,
        "step54Integrated": fields["security_step54_integrated"],
        "threatModelsPresent": {
            "baseline": fields["security_threat_model_present"],
            "agent": fields["security_agent_threat_model_present"],
            "supplyChain": fields["security_supply_chain_threat_model_present"],
            "runtimeGitops": fields["security_runtime_gitops_threat_model_present"],
        },
        "blockers": blockers,
        "requiredNextSteps": [
            "step_55_non_production_cluster_smoke",
            "step_56_real_argocd_manual_sync",
            "step_60_production_readiness_review",
        ],
    }


__all__ = [
    "section",
    "load_runtime_report",
    "integrated_safety_fields",
    "evidence_package_view",
    "release_risk_summary_view",
    "readiness_report_view",
    "step54_status_view",
]
