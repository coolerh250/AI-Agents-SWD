"""Step 56 -- read-only non-production ArgoCD manual-sync posture.

Reads the COMMITTED non-production ArgoCD manual-sync summary + plan / install
boundary / project policy under ``infra/gitops`` (copied into the orchestrator
image) and, optionally, the latest redacted runtime sync report under
``.runtime/gitops/`` (NEVER committed, absent in the image -> views note the report
is not present). Nothing here connects to a cluster, runs kubectl, installs, syncs,
or exposes a token / admin password / kubeconfig. Not a production-readiness claim.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from shared.sdk.secrets_foundation.secret_redaction import redact

ROOT = Path(__file__).resolve().parents[3]


def _load_yaml(rel: str, root: Path | None = None) -> dict[str, Any]:
    p = (root or ROOT) / "infra" / "gitops" / rel
    if not p.is_file():
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def _summary(root: Path | None = None) -> dict[str, Any]:
    return _load_yaml("nonproduction-argocd-manual-sync-summary.yaml", root).get(
        "nonProductionArgocdManualSyncSummary", {}
    )


def load_runtime_report(runtime_dir: Path | None = None) -> dict[str, Any] | None:
    base = runtime_dir or (ROOT / ".runtime" / "gitops")
    p = base / "nonproduction-argocd-manual-sync-report.json"
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return redact(data) if isinstance(data, dict) else None


def nonprod_argocd_safety_fields(root: Path | None = None) -> dict[str, Any]:
    s = _summary(root)
    return {
        "nonprod_argocd_enabled": bool(s.get("argocdEnabled", False)),
        "nonprod_argocd_namespace": s.get("argocdNamespace", ""),
        "nonprod_argocd_installed": bool(s.get("argocdInstalled", False)),
        "nonprod_argocd_project_created": bool(s.get("projectCreated", False)),
        "nonprod_argocd_application_created": bool(s.get("applicationCreated", False)),
        "nonprod_argocd_manual_sync_performed": bool(s.get("manualSyncPerformed", False)),
        "nonprod_argocd_manual_sync_succeeded": bool(s.get("manualSyncSucceeded", False)),
        "nonprod_argocd_auto_sync_enabled": bool(s.get("autoSyncEnabled", False)),
        "nonprod_argocd_prune_enabled": bool(s.get("pruneEnabled", False)),
        "nonprod_argocd_self_heal_enabled": bool(s.get("selfHealEnabled", False)),
        "nonprod_argocd_destination_namespace": s.get("destinationNamespace", ""),
        "nonprod_argocd_production_namespace_touched": bool(
            s.get("productionNamespaceTouched", False)
        ),
        "nonprod_argocd_public_ingress_enabled": bool(s.get("publicIngressEnabled", False)),
        "nonprod_argocd_loadbalancer_enabled": bool(s.get("loadBalancerEnabled", False)),
        "argocd_production_sync_performed": bool(s.get("argocdProductionSyncPerformed", False)),
    }


def _report_present(runtime_dir: Path | None = None) -> bool:
    return load_runtime_report(runtime_dir) is not None


def preflight_view(root: Path | None = None) -> dict[str, Any]:
    plan = _load_yaml("nonproduction-argocd-manual-sync-plan.yaml", root).get(
        "nonProductionArgocdManualSyncPlan", {}
    )
    return redact(
        {
            "cluster": plan.get("cluster", ""),
            "argocdNamespace": plan.get("argocdNamespace", ""),
            "destinationNamespace": plan.get("destinationNamespace", ""),
            "manualOnly": bool((plan.get("syncPolicy", {}) or {}).get("manualOnly", False)),
            "productionReady": False,
        }
    )


def install_view(root: Path | None = None) -> dict[str, Any]:
    b = _load_yaml("nonproduction-argocd-install-boundary.yaml", root).get(
        "nonProductionArgocdInstallBoundary", {}
    )
    s = _summary(root)
    return redact(
        {
            "namespace": b.get("namespace", ""),
            "version": b.get("version", ""),
            "installed": bool(s.get("argocdInstalled", False)),
            "serverServiceType": b.get("serverServiceType", ""),
            "publicIngress": bool(b.get("publicIngress", False)),
            "loadBalancer": bool(b.get("loadBalancer", False)),
            "ssoEnabled": bool(b.get("ssoEnabled", False)),
            "serverExposedExternally": bool(b.get("serverExposedExternally", False)),
            "adminTokenCommitted": bool(b.get("adminTokenCommitted", False)),
            "productionReady": False,
        }
    )


def project_view(root: Path | None = None) -> dict[str, Any]:
    p = (
        _load_yaml("nonproduction-argocd-project-policy.yaml", root)
        .get("nonProductionArgocdProjectPolicy", {})
        .get("project", {})
    )
    return redact(
        {
            "name": p.get("name", ""),
            "productionAllowed": bool(p.get("productionAllowed", False)),
            "destinations": p.get("destinations", []),
            "wildcardDestinationAllowed": bool(p.get("wildcardDestinationAllowed", False)),
            "clusterWideResourcesAllowed": bool(p.get("clusterWideResourcesAllowed", False)),
            "syncPolicy": p.get("syncPolicy", {}),
            "productionReady": False,
        }
    )


def application_view(root: Path | None = None) -> dict[str, Any]:
    s = _summary(root)
    return redact(
        {
            "application": s.get("application", ""),
            "project": s.get("project", ""),
            "destinationNamespace": s.get("destinationNamespace", ""),
            "autoSyncEnabled": bool(s.get("autoSyncEnabled", False)),
            "pruneEnabled": bool(s.get("pruneEnabled", False)),
            "selfHealEnabled": bool(s.get("selfHealEnabled", False)),
            "productionReady": False,
        }
    )


def sync_view(root: Path | None = None, runtime_dir: Path | None = None) -> dict[str, Any]:
    s = _summary(root)
    return redact(
        {
            "manualSyncPerformed": bool(s.get("manualSyncPerformed", False)),
            "manualSyncSucceeded": bool(s.get("manualSyncSucceeded", False)),
            "lastSyncStatus": s.get("lastSyncStatus", "not_run"),
            "lastHealthStatus": s.get("lastHealthStatus", "not_run"),
            "syncedResourceKinds": s.get("syncedResourceKinds", []),
            "liveReportPresent": _report_present(runtime_dir),
            "productionReady": False,
        }
    )


def safety_view(root: Path | None = None) -> dict[str, Any]:
    return redact(nonprod_argocd_safety_fields(root))


def report_view(root: Path | None = None, runtime_dir: Path | None = None) -> dict[str, Any]:
    report = load_runtime_report(runtime_dir)
    if report is None:
        s = _summary(root)
        return redact(
            {
                "status": "not_run",
                "note": "live runtime sync report is not committed / not in image",
                "committedSummaryStatus": s.get("lastSyncStatus", "not_run"),
                "productionReady": False,
            }
        )
    return report


def readiness_view(root: Path | None = None) -> dict[str, Any]:
    s = _summary(root)
    return redact(
        {
            "productionReady": False,
            "manualSyncSucceeded": bool(s.get("manualSyncSucceeded", False)),
            "autoSyncEnabled": bool(s.get("autoSyncEnabled", False)),
            "nextRequiredSteps": [
                "Step 57 -- Multi-project Delivery Capability & Work-item Dispatch",
            ],
            "caveat": "non-production manual sync only; not production GitOps / ArgoCD ready",
        }
    )
