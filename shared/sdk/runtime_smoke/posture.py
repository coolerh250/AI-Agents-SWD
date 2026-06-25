"""Step 55 -- read-only non-production Kubernetes runtime smoke posture.

Reads the COMMITTED smoke plan / namespace plan / report schema under
``infra/kubernetes`` and (optionally) the latest redacted runtime smoke report under
``.runtime/kubernetes/``. The runtime report is NEVER committed and is absent in the
orchestrator image, so the live views degrade to ``not_run`` and the safety fields
to the blocked/non-production defaults -- never a fake cluster-smoke PASS. Nothing
here connects to a cluster, runs kubectl/helm, deploys, or syncs ArgoCD.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from shared.sdk.secrets_foundation.secret_redaction import redact

ROOT = Path(__file__).resolve().parents[3]


def _load_yaml(name: str, root: Path | None = None) -> dict[str, Any]:
    p = (root or ROOT) / "infra" / "kubernetes" / name
    if not p.is_file():
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def section(name: str, root: Path | None = None) -> dict[str, Any]:
    return redact(_load_yaml(name, root))


def load_runtime_report(runtime_dir: Path | None = None) -> dict[str, Any] | None:
    base = runtime_dir or (ROOT / ".runtime" / "kubernetes")
    p = base / "nonproduction-runtime-smoke-report.json"
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return redact(data) if isinstance(data, dict) else None


def _section_status(report: dict[str, Any] | None, key: str) -> str:
    if not report:
        return "not_run"
    val = report.get(key)
    if isinstance(val, dict):
        return str(val.get("status", "not_run"))
    return "not_run"


def nonprod_runtime_safety_fields(
    root: Path | None = None, runtime_dir: Path | None = None
) -> dict[str, Any]:
    base = root or ROOT
    plan = _load_yaml("nonproduction-cluster-smoke-plan.yaml", base).get(
        "nonProductionRuntimeSmoke", {}
    )
    nsplan = _load_yaml("nonproduction-namespace-plan.yaml", base).get(
        "nonProductionNamespacePlan", {}
    )
    report = load_runtime_report(runtime_dir)
    ns = nsplan.get("namespace", "")
    smoke_enabled = bool(plan)

    if not report:
        return {
            "nonprod_kubernetes_smoke_enabled": smoke_enabled,
            "nonprod_cluster_access_detected": False,
            "nonprod_cluster_context_safe": False,
            "nonprod_namespace": ns,
            "nonprod_helm_install_attempted": False,
            "nonprod_helm_install_succeeded": False,
            "nonprod_pods_running": False,
            "nonprod_service_health_passed": False,
            "nonprod_connectivity_passed": False,
            "nonprod_networkpolicy_passed": False,
            "nonprod_storage_passed": False,
            "nonprod_securitycontext_passed": False,
            "nonprod_batch_job_smoke_passed": False,
            "nonprod_runtime_smoke_report_generated": False,
            "nonprod_runtime_smoke_production_ready": False,
            "kubernetes_production_deploy_performed": False,
            "argocd_sync_performed": False,
        }

    blocked = bool(report.get("blocked"))

    def passed(key: str) -> bool:
        return _section_status(report, key) == "passed"

    return {
        "nonprod_kubernetes_smoke_enabled": smoke_enabled,
        "nonprod_cluster_access_detected": not blocked,
        "nonprod_cluster_context_safe": not blocked,
        "nonprod_namespace": report.get("namespace") or ns,
        "nonprod_helm_install_attempted": bool(report.get("helmRelease")) and not blocked,
        "nonprod_helm_install_succeeded": passed("podStatus") and not blocked,
        "nonprod_pods_running": passed("podStatus"),
        "nonprod_service_health_passed": passed("serviceHealth"),
        "nonprod_connectivity_passed": passed("connectivity"),
        "nonprod_networkpolicy_passed": passed("networkPolicy"),
        "nonprod_storage_passed": passed("pvc"),
        "nonprod_securitycontext_passed": passed("securityContext"),
        "nonprod_batch_job_smoke_passed": passed("batchJobs"),
        "nonprod_runtime_smoke_report_generated": True,
        "nonprod_runtime_smoke_production_ready": False,
        "kubernetes_production_deploy_performed": False,
        "argocd_sync_performed": False,
    }


def _report_section_view(key: str, runtime_dir: Path | None = None) -> dict[str, Any]:
    report = load_runtime_report(runtime_dir)
    if report is None:
        return {"status": "not_run", "productionReady": False}
    val = report.get(key)
    if isinstance(val, dict):
        out = dict(val)
        out.setdefault("status", "not_run")
        out["productionReady"] = False
        return out
    return {"status": "not_run", "productionReady": False}


def preflight_view(runtime_dir: Path | None = None) -> dict[str, Any]:
    report = load_runtime_report(runtime_dir)
    if report is None:
        return {"status": "not_run", "blocked": True, "productionReady": False}
    return {
        "status": "blocked" if report.get("blocked") else "passed",
        "blocked": bool(report.get("blocked")),
        "blockedReason": report.get("blockedReason"),
        "clusterContextHash": report.get("clusterContextHash"),
        "productionReady": False,
    }


def namespace_view(root: Path | None = None) -> dict[str, Any]:
    return section("nonproduction-namespace-plan.yaml", root)


def helm_view(runtime_dir: Path | None = None) -> dict[str, Any]:
    report = load_runtime_report(runtime_dir)
    if report is None:
        return {"status": "not_run", "productionReady": False}
    return {
        "status": "blocked" if report.get("blocked") else "passed",
        "helmRelease": report.get("helmRelease"),
        "chartVersion": report.get("chartVersion"),
        "imageRefs": report.get("imageRefs", []),
        "productionReady": False,
    }


def report_view(runtime_dir: Path | None = None) -> dict[str, Any]:
    report = load_runtime_report(runtime_dir)
    if report is None:
        return {"status": "not_run", "productionReady": False}
    report["productionReady"] = False
    return report


def readiness_view(root: Path | None = None, runtime_dir: Path | None = None) -> dict[str, Any]:
    fields = nonprod_runtime_safety_fields(root, runtime_dir)
    blockers: list[str] = []
    if not fields["nonprod_cluster_access_detected"]:
        blockers.append("no_safe_nonproduction_cluster")
    if not fields["nonprod_helm_install_succeeded"]:
        blockers.append("helm_runtime_smoke_not_completed")
    blockers.append("real_argocd_manual_sync_required_step_56")
    return {
        "status": "framework_ready",
        "productionReady": False,
        "clusterAccessDetected": fields["nonprod_cluster_access_detected"],
        "namespace": fields["nonprod_namespace"],
        "blockers": blockers,
        "requiredNextSteps": [
            "step_56_real_argocd_nonproduction_manual_sync",
            "step_60_production_readiness_review",
        ],
    }


__all__ = [
    "section",
    "load_runtime_report",
    "nonprod_runtime_safety_fields",
    "preflight_view",
    "namespace_view",
    "helm_view",
    "report_view",
    "readiness_view",
    "_report_section_view",
]
