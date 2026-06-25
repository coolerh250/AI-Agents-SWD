"""Step 55 -- non-production runtime smoke operations API surface."""

from __future__ import annotations

import runtime_baseline_api as m

EXPECTED = {
    "/operations/runtime/nonprod-smoke/preflight",
    "/operations/runtime/nonprod-smoke/namespace",
    "/operations/runtime/nonprod-smoke/helm",
    "/operations/runtime/nonprod-smoke/pods",
    "/operations/runtime/nonprod-smoke/services",
    "/operations/runtime/nonprod-smoke/connectivity",
    "/operations/runtime/nonprod-smoke/networkpolicy",
    "/operations/runtime/nonprod-smoke/storage",
    "/operations/runtime/nonprod-smoke/securitycontext",
    "/operations/runtime/nonprod-smoke/batch-jobs",
    "/operations/runtime/nonprod-smoke/report",
    "/operations/runtime/nonprod-smoke/readiness",
}


def test_expected_endpoints_present() -> None:
    paths = {getattr(r, "path", "") for r in m.router.routes}
    assert EXPECTED <= paths


def test_readiness_not_production_ready() -> None:
    from shared.sdk.runtime_smoke import readiness_view

    v = readiness_view()
    assert v["productionReady"] is False
    assert v["blockers"]


def test_views_degrade_to_not_run(tmp_path) -> None:
    from shared.sdk.runtime_smoke import helm_view, preflight_view, report_view

    empty = tmp_path / "k"
    empty.mkdir()
    assert report_view(runtime_dir=empty)["status"] == "not_run"
    assert helm_view(runtime_dir=empty)["status"] == "not_run"
    assert preflight_view(runtime_dir=empty)["blocked"] is True
