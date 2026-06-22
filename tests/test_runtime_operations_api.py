"""Step 51.4 -- read-only runtime operations API (router-level)."""

from __future__ import annotations

import runtime_baseline_api as rt

EXPECTED_PATHS = {
    "/operations/runtime/kubernetes/baseline",
    "/operations/runtime/kubernetes/components",
    "/operations/runtime/kubernetes/security",
    "/operations/runtime/kubernetes/network",
    "/operations/runtime/kubernetes/storage",
    "/operations/runtime/kubernetes/batch-jobs",
    "/operations/runtime/helm/status",
    "/operations/runtime/gitops/status",
    "/operations/runtime/argocd/status",
    "/operations/runtime/environments",
    "/operations/runtime/readiness",
    "/operations/runtime/report",
}


def test_twelve_get_endpoints() -> None:
    paths = {getattr(r, "path", None) for r in rt.router.routes}
    assert paths == EXPECTED_PATHS


def test_all_routes_get_only() -> None:
    for route in rt.router.routes:
        assert set(getattr(route, "methods", None) or set()) <= {"GET", "HEAD"}, getattr(
            route, "path", "?"
        )


def test_baseline_reports_validated_not_deployed() -> None:
    d = rt.runtime_kubernetes_baseline()
    assert d["status"] == "validated_not_deployed"
    assert d["clusterConnected"] is False


def test_readiness_not_production_ready() -> None:
    d = rt.runtime_readiness()
    assert d["productionReady"] is False
    assert d["validatedNotDeployed"] is True
    assert d["realDeployEnabled"] is False


def test_report_has_safety_block() -> None:
    d = rt.runtime_report()
    assert d["safety"]["runtime_production_ready"] is False
    assert d["safety"]["kubernetes_cluster_connected"] is False
