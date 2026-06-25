"""Step 51.4 -- read-only Kubernetes / Helm / GitOps runtime baseline API.

GET-only visibility over the COMMITTED Step 51 static baseline summary. NO write
endpoints, NO deploy/sync/apply/install, NO cluster read, NO verifier execution,
NO user-provided path/command. If the summary is absent the API returns
``status: unknown`` -- never a fake PASS. Responses carry statuses / counts /
names only (no secrets, no rendered manifests, no chain-of-thought).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter

from shared.sdk.runtime_baseline import (
    load_runtime_baseline_summary,
    runtime_baseline_safety_fields,
)
from shared.sdk.runtime_smoke import posture as smoke_posture

router = APIRouter(prefix="/operations/runtime", tags=["runtime-baseline"])

# Resolved relative to the orchestrator working dir (/app in-container, repo root
# locally). The file is committed + copied into the image; never user-provided.
_SUMMARY_PATH = Path("infra/kubernetes/runtime-baseline-summary.yaml")

_UNKNOWN_BASELINE: dict[str, Any] = {
    "status": "unknown",
    "clusterConnected": False,
    "areaStatus": {},
    "markerSummary": {"total": 0, "markers": []},
    "productionSafety": {
        "productionReady": False,
        "validatedNotDeployed": False,
        "realDeployEnabled": False,
        "productionApplicationEnabled": False,
        "autoSyncEnabled": False,
    },
    "safetyFacts": {},
    "environments": [],
    "limitations": [],
    "nextRequiredSteps": [],
}


def _summary() -> dict[str, Any]:
    return load_runtime_baseline_summary(_SUMMARY_PATH) or dict(_UNKNOWN_BASELINE)


@router.get("/kubernetes/baseline")
def runtime_kubernetes_baseline() -> dict:
    s = _summary()
    return {
        "status": s.get("status", "unknown"),
        "clusterConnected": s.get("clusterConnected", False),
        "areaStatus": s.get("areaStatus", {}),
        "productionSafety": s.get("productionSafety", {}),
        "markerSummary": s.get("markerSummary", {}),
        "limitations": s.get("limitations", []),
        "nextRequiredSteps": s.get("nextRequiredSteps", []),
    }


@router.get("/kubernetes/components")
def runtime_kubernetes_components() -> dict:
    s = _summary()
    return {
        "componentCount": s.get("componentCount", 0),
        "dependencyEdgeCount": s.get("dependencyEdgeCount", 0),
        "status": s.get("status", "unknown"),
    }


@router.get("/kubernetes/security")
def runtime_kubernetes_security() -> dict:
    s = _summary()
    areas = s.get("areaStatus", {})
    return {
        "workloadSecurityStatus": areas.get("workloadSecurity", "unknown"),
        "rbacStatus": areas.get("rbac", "unknown"),
        "safetyFacts": s.get("safetyFacts", {}),
    }


@router.get("/kubernetes/network")
def runtime_kubernetes_network() -> dict:
    s = _summary()
    facts = s.get("safetyFacts", {})
    return {
        "networkPolicyStatus": s.get("areaStatus", {}).get("networkPolicy", "unknown"),
        "defaultDenyEnabled": facts.get("defaultDenyEnabled", False),
        "externalEgressEnabled": facts.get("externalEgressEnabled", False),
    }


@router.get("/kubernetes/storage")
def runtime_kubernetes_storage() -> dict:
    s = _summary()
    return {"storageStatus": s.get("areaStatus", {}).get("storage", "unknown")}


@router.get("/kubernetes/batch-jobs")
def runtime_kubernetes_batch_jobs() -> dict:
    s = _summary()
    return {"batchJobsStatus": s.get("areaStatus", {}).get("batchJobs", "unknown")}


@router.get("/helm/status")
def runtime_helm_status() -> dict:
    s = _summary()
    return {"helmStatus": s.get("areaStatus", {}).get("helm", "unknown")}


@router.get("/gitops/status")
def runtime_gitops_status() -> dict:
    s = _summary()
    return {"gitopsStatus": s.get("areaStatus", {}).get("gitops", "unknown")}


@router.get("/argocd/status")
def runtime_argocd_status() -> dict:
    s = _summary()
    prod = s.get("productionSafety", {})
    return {
        "gitopsStatus": s.get("areaStatus", {}).get("gitops", "unknown"),
        "autoSyncEnabled": prod.get("autoSyncEnabled", False),
        "productionApplicationEnabled": prod.get("productionApplicationEnabled", False),
        "realSyncPerformed": False,
    }


@router.get("/environments")
def runtime_environments() -> dict:
    return {"environments": _summary().get("environments", [])}


@router.get("/readiness")
def runtime_readiness() -> dict:
    s = _summary()
    prod = s.get("productionSafety", {})
    return {
        "status": s.get("status", "unknown"),
        "productionReady": False,
        "validatedNotDeployed": prod.get("validatedNotDeployed", False),
        "realDeployEnabled": prod.get("realDeployEnabled", False),
        "limitations": s.get("limitations", []),
        "nextRequiredSteps": s.get("nextRequiredSteps", []),
    }


@router.get("/report")
def runtime_report() -> dict:
    s = _summary()
    return {
        "status": s.get("status", "unknown"),
        "clusterConnected": s.get("clusterConnected", False),
        "componentCount": s.get("componentCount", 0),
        "dependencyEdgeCount": s.get("dependencyEdgeCount", 0),
        "areaStatus": s.get("areaStatus", {}),
        "productionSafety": s.get("productionSafety", {}),
        "safetyFacts": s.get("safetyFacts", {}),
        "environments": s.get("environments", []),
        "markerSummary": s.get("markerSummary", {}),
        "limitations": s.get("limitations", []),
        "nextRequiredSteps": s.get("nextRequiredSteps", []),
        "safety": runtime_baseline_safety_fields(None if s.get("status") == "unknown" else s),
    }


# ---------------------------------------------------------------------------
# Step 55 -- read-only non-production Kubernetes runtime smoke posture. GET-only.
# NO deploy / helm-install / cleanup / kubectl-exec / ArgoCD-sync endpoint, NO
# arbitrary namespace / command. Runtime smoke artifacts are NEVER committed and
# are absent in the image, so live views degrade to not_run. No kubeconfig / token
# / cert / secret / rendered manifest is ever returned.
# ---------------------------------------------------------------------------


@router.get("/nonprod-smoke/preflight")
def nonprod_smoke_preflight() -> dict:
    return smoke_posture.preflight_view()


@router.get("/nonprod-smoke/namespace")
def nonprod_smoke_namespace() -> dict:
    return smoke_posture.namespace_view()


@router.get("/nonprod-smoke/helm")
def nonprod_smoke_helm() -> dict:
    return smoke_posture.helm_view()


@router.get("/nonprod-smoke/pods")
def nonprod_smoke_pods() -> dict:
    return smoke_posture._report_section_view("podStatus")


@router.get("/nonprod-smoke/services")
def nonprod_smoke_services() -> dict:
    return smoke_posture._report_section_view("serviceHealth")


@router.get("/nonprod-smoke/connectivity")
def nonprod_smoke_connectivity() -> dict:
    return smoke_posture._report_section_view("connectivity")


@router.get("/nonprod-smoke/networkpolicy")
def nonprod_smoke_networkpolicy() -> dict:
    return smoke_posture._report_section_view("networkPolicy")


@router.get("/nonprod-smoke/storage")
def nonprod_smoke_storage() -> dict:
    return smoke_posture._report_section_view("pvc")


@router.get("/nonprod-smoke/securitycontext")
def nonprod_smoke_securitycontext() -> dict:
    return smoke_posture._report_section_view("securityContext")


@router.get("/nonprod-smoke/batch-jobs")
def nonprod_smoke_batch_jobs() -> dict:
    return smoke_posture._report_section_view("batchJobs")


@router.get("/nonprod-smoke/report")
def nonprod_smoke_report() -> dict:
    return smoke_posture.report_view()


@router.get("/nonprod-smoke/readiness")
def nonprod_smoke_readiness() -> dict:
    return smoke_posture.readiness_view()


__all__ = ["router"]
