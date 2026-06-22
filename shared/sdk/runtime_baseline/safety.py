"""Step 51.4 -- flat /operations/safety fields for the runtime baseline.

Booleans / enums / counts only. When no summary is available the fields default
to a SAFE, non-production posture (not connected, not ready) with `unknown`
statuses -- never a fake PASS.
"""

from __future__ import annotations

from typing import Any

_UNKNOWN = "unknown"


def runtime_baseline_safety_fields(summary: dict[str, Any] | None) -> dict[str, Any]:
    if not summary:
        areas: dict[str, Any] = {}
        facts: dict[str, Any] = {}
        prod: dict[str, Any] = {}
        status = _UNKNOWN
    else:
        areas = summary.get("areaStatus", {}) or {}
        facts = summary.get("safetyFacts", {}) or {}
        prod = summary.get("productionSafety", {}) or {}
        status = summary.get("status", _UNKNOWN)

    def area(name: str) -> str:
        return areas.get(name, _UNKNOWN)

    return {
        # baseline + cluster-operation facts (always false: never connected/run)
        "kubernetes_runtime_baseline_enabled": True,
        "kubernetes_runtime_baseline_status": status,
        "kubernetes_cluster_connected": bool(summary and summary.get("clusterConnected")),
        "kubernetes_kubectl_executed": False,
        "kubernetes_helm_install_executed": False,
        "kubernetes_helm_upgrade_executed": False,
        "kubernetes_argocd_sync_executed": False,
        # helm
        "helm_chart_present": area("helm") == "passed",
        "helm_chart_lint_status": area("helm"),
        "helm_environment_render_status": area("helm"),
        "helm_values_schema_valid": area("helm") == "passed",
        "helm_prod_placeholder_fail_closed": bool(prod.get("validatedNotDeployed")),
        # per-area
        "kubernetes_workload_security_status": area("workloadSecurity"),
        "kubernetes_rbac_safety_status": area("rbac"),
        "kubernetes_network_policy_status": area("networkPolicy"),
        "kubernetes_storage_baseline_status": area("storage"),
        "kubernetes_batch_jobs_status": area("batchJobs"),
        # structural safety facts
        "kubernetes_default_deny_enabled": bool(facts.get("defaultDenyEnabled")),
        "kubernetes_external_egress_enabled": bool(facts.get("externalEgressEnabled")),
        "kubernetes_hostpath_present": bool(facts.get("hostPathPresent")),
        "kubernetes_privileged_workload_present": bool(facts.get("privilegedWorkloadPresent")),
        "kubernetes_cluster_admin_present": bool(facts.get("clusterAdminPresent")),
        "kubernetes_serviceaccount_token_mounted": bool(facts.get("serviceAccountTokenMounted")),
        "kubernetes_embedded_secret_detected": bool(facts.get("embeddedSecretDetected")),
        # gitops
        "gitops_baseline_enabled": True,
        "gitops_argocd_manifests_status": area("gitops"),
        "gitops_environment_mapping_status": area("gitops"),
        "gitops_production_isolation_status": area("gitops"),
        "argocd_auto_sync_enabled": bool(prod.get("autoSyncEnabled")),
        "argocd_prod_application_enabled": bool(prod.get("productionApplicationEnabled")),
        "argocd_real_sync_performed": False,
        # runtime readiness
        "runtime_real_deploy_enabled": bool(prod.get("realDeployEnabled")),
        "runtime_production_ready": False,
        "runtime_validated_not_deployed": bool(prod.get("validatedNotDeployed")),
        "runtime_non_production_limitations": (
            list(summary.get("limitations", [])) if summary else []
        ),
    }
