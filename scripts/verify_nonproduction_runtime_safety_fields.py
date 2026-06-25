#!/usr/bin/env python3
"""Step 55 -- non-production runtime smoke /operations/safety fields verifier.

Asserts the Step 55 fields carry a non-production posture. With no safe cluster the
smoke-result fields are false (blocked); the production-critical invariants
(production_ready false, production deploy false, argocd sync false,
production_executed_true_count=0) hold regardless.

Marker: NONPROD_RUNTIME_SAFETY_FIELDS_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000").rstrip("/")

EXPECT_TRUE = ["nonprod_kubernetes_smoke_enabled"]
# In the no-safe-cluster (blocked) state these are all false.
EXPECT_FALSE = [
    "nonprod_cluster_access_detected",
    "nonprod_cluster_context_safe",
    "nonprod_helm_install_attempted",
    "nonprod_helm_install_succeeded",
    "nonprod_pods_running",
    "nonprod_service_health_passed",
    "nonprod_connectivity_passed",
    "nonprod_networkpolicy_passed",
    "nonprod_storage_passed",
    "nonprod_securitycontext_passed",
    "nonprod_batch_job_smoke_passed",
    "nonprod_runtime_smoke_report_generated",
    "nonprod_runtime_smoke_production_ready",
    "kubernetes_production_deploy_performed",
    "argocd_sync_performed",
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
        bad(f"/operations/safety not reachable at {BASE}: {e}")
        print("NONPROD_RUNTIME_SAFETY_FIELDS_VERIFY: FAIL")
        return 1

    all_fields = (
        EXPECT_TRUE + EXPECT_FALSE + ["nonprod_namespace", "production_executed_true_count"]
    )
    missing = [f for f in all_fields if f not in data]
    if missing:
        bad(f"missing runtime smoke safety fields: {missing}")
    else:
        ok(f"all {len(all_fields)} runtime smoke safety fields present")

    for f in EXPECT_TRUE:
        if data.get(f) is not True:
            bad(f"{f} must be true, got {data.get(f)!r}")
    if not [x for x in failures if "must be true" in x]:
        ok("nonprod_kubernetes_smoke_enabled=true (framework present)")

    for f in EXPECT_FALSE:
        if data.get(f) is not False:
            bad(f"{f} must be false, got {data.get(f)!r}")
    if not [x for x in failures if "must be false" in x]:
        ok("cluster/smoke result + production deploy/sync/ready fields all false (blocked)")

    ns = str(data.get("nonprod_namespace", ""))
    if "prod" in ns.lower():
        bad(f"nonprod_namespace looks production: {ns!r}")
    else:
        ok(f"nonprod_namespace non-production: {ns!r}")

    if data.get("production_executed_true_count") not in (0, None):
        bad(
            f"production_executed_true_count must be 0, got {data.get('production_executed_true_count')}"
        )
    else:
        ok("production_executed_true_count=0")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("NONPROD_RUNTIME_SAFETY_FIELDS_VERIFY: FAIL")
        return 1
    print("NONPROD_RUNTIME_SAFETY_FIELDS_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
