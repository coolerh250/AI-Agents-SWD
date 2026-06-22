#!/usr/bin/env python3
"""Step 51.4 -- /operations/safety runtime field verifier.

Asserts the Kubernetes / Helm / GitOps runtime baseline fields exist on
/operations/safety with the expected non-production posture (not connected, not
ready, no auto-sync, no hostPath/privileged/cluster-admin/secret) and
production_executed_true_count=0. Live HTTP check. No cluster.

Marker: RUNTIME_SAFETY_FIELDS_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000").rstrip("/")

EXPECT_TRUE = [
    "kubernetes_runtime_baseline_enabled",
    "helm_chart_present",
    "helm_values_schema_valid",
    "helm_prod_placeholder_fail_closed",
    "kubernetes_default_deny_enabled",
    "gitops_baseline_enabled",
    "runtime_validated_not_deployed",
]
EXPECT_FALSE = [
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
]
EXPECT_PASSED = [
    "helm_chart_lint_status",
    "helm_environment_render_status",
    "kubernetes_workload_security_status",
    "kubernetes_rbac_safety_status",
    "kubernetes_network_policy_status",
    "kubernetes_storage_baseline_status",
    "kubernetes_batch_jobs_status",
    "gitops_argocd_manifests_status",
    "gitops_environment_mapping_status",
    "gitops_production_isolation_status",
]

failures: list[str] = []
passes: list[str] = []


def ok(m: str) -> None:
    passes.append(m)
    print(f"  [PASS] {m}")


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    try:
        with urllib.request.urlopen(BASE + "/operations/safety", timeout=10) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as e:
        bad(f"orchestrator /operations/safety not reachable at {BASE}: {e}")
        print("RUNTIME_SAFETY_FIELDS_VERIFY: FAIL")
        return 1

    for k in EXPECT_TRUE:
        if data.get(k) is not True:
            bad(f"{k} must be true (got {data.get(k)})")
    for k in EXPECT_FALSE:
        if data.get(k) is not False:
            bad(f"{k} must be false (got {data.get(k)})")
    for k in EXPECT_PASSED:
        if data.get(k) != "passed":
            bad(f"{k} must be 'passed' (got {data.get(k)})")
    if data.get("kubernetes_runtime_baseline_status") not in (
        "validated_not_deployed",
        "passed_with_non_production_limitations",
    ):
        bad(
            f"kubernetes_runtime_baseline_status unexpected: {data.get('kubernetes_runtime_baseline_status')}"
        )
    if (
        data.get("production_executed_true_count") not in (0, None)
        and data.get("production_executed_true_count") != 0
    ):
        bad(
            f"production_executed_true_count must be 0 (got {data.get('production_executed_true_count')})"
        )
    lims = data.get("runtime_non_production_limitations")
    if not isinstance(lims, list) or not lims:
        bad("runtime_non_production_limitations must be a non-empty list")

    if not failures:
        ok("all runtime safety fields present with the expected non-production posture")
        ok(
            "production_executed_true_count=0; runtime_production_ready=false; validated_not_deployed=true"
        )

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("RUNTIME_SAFETY_FIELDS_VERIFY: FAIL")
        return 1
    print("RUNTIME_SAFETY_FIELDS_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
