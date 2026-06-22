"""Step 51.4 -- runtime baseline safety fields."""

from __future__ import annotations

from pathlib import Path

from shared.sdk.runtime_baseline import (
    load_runtime_baseline_summary,
    runtime_baseline_safety_fields,
)

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "infra" / "kubernetes" / "runtime-baseline-summary.yaml"


def _fields() -> dict:
    return runtime_baseline_safety_fields(load_runtime_baseline_summary(SUMMARY))


def test_expected_true_fields() -> None:
    f = _fields()
    for k in (
        "kubernetes_runtime_baseline_enabled",
        "helm_chart_present",
        "helm_values_schema_valid",
        "helm_prod_placeholder_fail_closed",
        "kubernetes_default_deny_enabled",
        "gitops_baseline_enabled",
        "runtime_validated_not_deployed",
    ):
        assert f[k] is True, k


def test_expected_false_fields() -> None:
    f = _fields()
    for k in (
        "kubernetes_cluster_connected",
        "kubernetes_kubectl_executed",
        "kubernetes_helm_install_executed",
        "kubernetes_helm_upgrade_executed",
        "kubernetes_argocd_sync_executed",
        "kubernetes_external_egress_enabled",
        "kubernetes_hostpath_present",
        "kubernetes_privileged_workload_present",
        "kubernetes_cluster_admin_present",
        "kubernetes_serviceaccount_token_mounted",
        "kubernetes_embedded_secret_detected",
        "argocd_auto_sync_enabled",
        "argocd_prod_application_enabled",
        "argocd_real_sync_performed",
        "runtime_real_deploy_enabled",
        "runtime_production_ready",
    ):
        assert f[k] is False, k


def test_expected_passed_statuses() -> None:
    f = _fields()
    for k in (
        "kubernetes_workload_security_status",
        "kubernetes_rbac_safety_status",
        "kubernetes_network_policy_status",
        "kubernetes_storage_baseline_status",
        "kubernetes_batch_jobs_status",
        "gitops_argocd_manifests_status",
    ):
        assert f[k] == "passed", k
    assert f["kubernetes_runtime_baseline_status"] == "validated_not_deployed"


def test_limitations_non_empty() -> None:
    assert _fields()["runtime_non_production_limitations"]


def test_missing_summary_safe_unknown() -> None:
    f = runtime_baseline_safety_fields(None)
    assert f["kubernetes_runtime_baseline_status"] == "unknown"
    assert f["runtime_production_ready"] is False
    assert f["kubernetes_cluster_connected"] is False
