"""Step 51.4 -- runtime baseline collector (read-only, no cluster).

`collect_runtime_baseline(root)` reads the committed Step 51 inventories,
catalogs, chart values and GitOps manifests and derives a redacted, structural
summary: per-area status + safety facts + limitations. It performs NO cluster
operation and runs NO verifier; the per-area status reflects the committed
source the verifiers also check.

`build_runtime_baseline_summary(root)` returns the serializable summary that is
committed to `infra/kubernetes/runtime-baseline-summary.yaml` and copied into the
orchestrator image; `load_runtime_baseline_summary(path)` reads it back (used by
the read-only operations API in-container).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

# The full Step 51 marker set surfaced by the runtime baseline (names only).
RUNTIME_BASELINE_MARKERS = [
    "KUBERNETES_RUNTIME_INVENTORY_VERIFY",
    "HELM_FOUNDATION_VERIFY",
    "KUBERNETES_WORKLOAD_SECURITY_VERIFY",
    "KUBERNETES_RBAC_SAFETY_VERIFY",
    "KUBERNETES_SECURITY_RBAC_BASELINE_VERIFY",
    "KUBERNETES_NETWORK_TOPOLOGY_VERIFY",
    "KUBERNETES_NETWORK_POLICY_VERIFY",
    "KUBERNETES_SERVICE_CONNECTIVITY_VERIFY",
    "KUBERNETES_NETWORK_BASELINE_VERIFY",
    "KUBERNETES_STORAGE_INVENTORY_VERIFY",
    "KUBERNETES_DATA_LIFECYCLE_VERIFY",
    "KUBERNETES_STORAGE_MANIFEST_VERIFY",
    "KUBERNETES_STORAGE_BASELINE_VERIFY",
    "KUBERNETES_BATCH_OPERATION_INVENTORY_VERIFY",
    "KUBERNETES_MIGRATION_JOB_VERIFY",
    "KUBERNETES_BACKUP_CRONJOB_VERIFY",
    "KUBERNETES_RESTORE_JOB_VERIFY",
    "KUBERNETES_BATCH_JOB_POLICY_VERIFY",
    "KUBERNETES_BATCH_JOBS_BASELINE_VERIFY",
    "ARGOCD_MANIFESTS_VERIFY",
    "GITOPS_ENVIRONMENT_MAPPING_VERIFY",
    "GITOPS_PRODUCTION_ISOLATION_VERIFY",
    "GITOPS_ARGOCD_BASELINE_VERIFY",
    "RUNTIME_OPERATIONS_VISIBILITY_VERIFY",
    "ADMIN_CONSOLE_RUNTIME_BASELINE_VERIFY",
    "RUNTIME_SAFETY_FIELDS_VERIFY",
    "KUBERNETES_HELM_ARGOCD_BASELINE_VERIFY",
]

NON_PRODUCTION_LIMITATIONS = [
    "no_kubernetes_cluster_connected",
    "no_helm_install_or_upgrade",
    "no_argocd_installed_or_sync",
    "no_real_destination_cluster",
    "no_repo_credentials",
    "no_production_oidc",
    "no_production_secret_store",
    "no_image_digest_pinning",
    "no_real_cloud_backup_target",
    "no_production_backup_schedule",
    "no_production_restore_approval",
    "no_workspace_production_rwx_or_object_storage",
    "first_party_images_require_non_root_cluster_smoke",
    "job_images_require_container_native_pg_dump_psql_smoke",
    "no_runtime_cluster_smoke",
    "no_real_pager_escalation",
]

NEXT_REQUIRED_STEPS = [
    "install_real_argocd_and_wire_real_destinations",
    "provision_production_oidc_secret_store_and_image_digests",
    "run_cluster_smoke_for_non_root_and_job_images",
    "operator_approval_before_any_production_sync",
]

CHART_REL = "infra/kubernetes/charts/ai-agents-platform"
SUMMARY_REL = "infra/kubernetes/runtime-baseline-summary.yaml"
_SECRET_VALUE = re.compile(
    r"(ghp_[A-Za-z0-9]{20,}|BEGIN [A-Z ]*PRIVATE KEY|AKIA[0-9A-Z]{16}|"
    r"(password|secret[_-]?key|token)\s*[:=]\s*[A-Za-z0-9/+=._-]{8,})",
    re.IGNORECASE,
)


def _load(p: Path) -> Any:
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def _merge(a: dict, b: dict) -> dict:
    out = dict(a)
    for k, v in (b or {}).items():
        out[k] = _merge(a[k], v) if isinstance(v, dict) and isinstance(a.get(k), dict) else v
    return out


def _status(ok: bool) -> str:
    return "passed" if ok else "failed"


def collect_runtime_baseline(root: Path) -> dict[str, Any]:
    """Aggregate the committed Step 51 baseline into a redacted summary."""
    k8s = root / "infra" / "kubernetes"
    chart = root / CHART_REL
    gitops = root / "infra" / "gitops"

    inv = _load(k8s / "runtime-inventory.yaml")
    matrix = _load(k8s / "runtime-dependency-matrix.yaml")
    storage_cat = _load(k8s / "storage-ownership-catalog.yaml")
    batch_inv = _load(k8s / "batch-operation-inventory.yaml")
    gitops_env = _load(gitops / "gitops-environments.yaml")
    values = _load(chart / "values.yaml")

    # ---- structural source scans (no cluster) ----
    # validate-values.yaml is policy logic that NAMES the forbidden tokens in its
    # fail guards; exclude it from the literal scan (mirrors the verifier pattern).
    template_text = "\n".join(
        p.read_text(encoding="utf-8")
        for p in (chart / "templates").glob("*.yaml")
        if p.name != "validate-values.yaml"
    )
    values_text = (chart / "values.yaml").read_text(encoding="utf-8")
    gitops_text = "\n".join(p.read_text(encoding="utf-8") for p in gitops.rglob("*.yaml"))

    # a real hostPath volume is a `hostPath:` mapping key, not the word in a comment
    hostpath_present = bool(re.search(r"hostPath:", template_text))
    privileged_present = bool(re.search(r"privileged:\s*true", template_text))
    cluster_admin_present = bool(
        re.search(r"kind:\s*(ClusterRole|ClusterRoleBinding)\b", template_text + gitops_text)
    )
    sa_token_mounted = (
        values["serviceAccount"]["automountServiceAccountToken"] is True
        or values["global"]["workloadSecurity"]["automountServiceAccountToken"] is True
    )
    embedded_secret = bool(_SECRET_VALUE.search(values_text)) or bool(
        re.search(r"^kind:\s*Secret", template_text, re.MULTILINE)
    )
    default_deny = bool(
        values["networkPolicy"]["defaultDenyIngress"]
        and values["networkPolicy"]["defaultDenyEgress"]
    )
    external_egress = values["networkPolicy"]["externalEgress"]["enabled"] is True
    drop_all = "ALL" in values["global"]["workloadSecurity"]["dropCapabilities"]

    # GitOps facts
    apps = [_load(p) for p in (gitops / "argocd" / "applications").glob("*.yaml")]
    auto_sync = any("automated" in (a.get("spec", {}).get("syncPolicy", {}) or {}) for a in apps)
    prod_env = gitops_env["environments"]["production-placeholder"]
    prod_app_enabled = bool(prod_env.get("active")) and not prod_env.get("disabled")

    # Production-merged values (fail-closed checks)
    prod_values = _merge(values, _load(chart / "values-prod-placeholder.yaml"))
    prod_real_deploy = prod_values["global"]["realDeployEnabled"] is True

    # ---- per-area status ----
    helm_ok = (chart / "Chart.yaml").is_file() and (chart / "values.schema.json").is_file()
    workload_ok = (
        (not hostpath_present) and (not privileged_present) and drop_all and (not sa_token_mounted)
    )
    rbac_ok = not cluster_admin_present
    network_ok = default_deny and (not external_egress)
    storage_ok = (
        storage_cat["stores"]["postgres-data"]["strategyByEnvironment"]["production"]
        == "externalService"
    )
    batch_ok = all(o.get("productionAllowed") is False for o in batch_inv["operations"])
    gitops_ok = (not auto_sync) and (not prod_app_enabled) and (not prod_real_deploy)

    areas = {
        "helm": _status(helm_ok),
        "workloadSecurity": _status(workload_ok),
        "rbac": _status(rbac_ok),
        "networkPolicy": _status(network_ok),
        "storage": _status(storage_ok),
        "batchJobs": _status(batch_ok),
        "gitops": _status(gitops_ok),
    }
    all_ok = all(v == "passed" for v in areas.values()) and not embedded_secret

    summary: dict[str, Any] = {
        "version": "1",
        "meta": {"stage": "53G", "step": "51.4"},
        "status": "validated_not_deployed" if all_ok else "failed",
        "clusterConnected": False,
        "componentCount": len(inv.get("services", inv.get("components", []) or []))
        or _count_components(inv),
        "dependencyEdgeCount": len(matrix.get("dependencies", [])),
        "areaStatus": areas,
        "markerSummary": {
            "total": len(RUNTIME_BASELINE_MARKERS),
            "markers": RUNTIME_BASELINE_MARKERS,
        },
        "environments": [
            {
                "name": name,
                "active": bool(e.get("active")),
                "disabled": bool(e.get("disabled")),
                "production": bool(e.get("production")),
                "valuesFile": e.get("valuesFile"),
                "automatedSync": bool(e.get("automatedSync")),
            }
            for name, e in gitops_env["environments"].items()
        ],
        "productionSafety": {
            "realDeployEnabled": prod_real_deploy,
            "productionReady": False,
            "validatedNotDeployed": all_ok,
            "productionApplicationEnabled": prod_app_enabled,
            "autoSyncEnabled": auto_sync,
        },
        "safetyFacts": {
            "hostPathPresent": hostpath_present,
            "privilegedWorkloadPresent": privileged_present,
            "clusterAdminPresent": cluster_admin_present,
            "serviceAccountTokenMounted": sa_token_mounted,
            "embeddedSecretDetected": embedded_secret,
            "defaultDenyEnabled": default_deny,
            "externalEgressEnabled": external_egress,
        },
        "limitations": list(NON_PRODUCTION_LIMITATIONS),
        "nextRequiredSteps": list(NEXT_REQUIRED_STEPS),
    }
    return summary


def _count_components(inv: dict) -> int:
    comps = inv.get("components")
    if isinstance(comps, dict):
        return len(comps)
    if isinstance(comps, list):
        return len(comps)
    return 0


def build_runtime_baseline_summary(root: Path) -> dict[str, Any]:
    return collect_runtime_baseline(root)


def load_runtime_baseline_summary(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, yaml.YAMLError):
        return None
