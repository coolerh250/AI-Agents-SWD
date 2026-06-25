"""Step 54.4 -- integrated security operations API surface."""

from __future__ import annotations

import security_posture_api as sp

EXPECTED = {
    "/operations/security/threat-model/baseline",
    "/operations/security/threat-model/agent",
    "/operations/security/threat-model/supply-chain",
    "/operations/security/threat-model/runtime-gitops",
    "/operations/security/release-risk/model",
    "/operations/security/release-risk/summary",
    "/operations/security/evidence/package",
    "/operations/security/readiness/report",
    "/operations/security/step54/status",
}


def test_expected_endpoints_present() -> None:
    paths = {getattr(r, "path", "") for r in sp.router.routes}
    assert EXPECTED <= paths


def test_step54_status_not_production_ready() -> None:
    from shared.sdk.security_integrated import step54_status_view

    v = step54_status_view()
    assert v["productionReady"] is False
    assert v["releaseGateEnabled"] is False
    assert v["blockers"]


def test_runtime_views_degrade_to_not_run_when_absent(tmp_path) -> None:
    from shared.sdk.security_integrated import (
        evidence_package_view,
        readiness_report_view,
        release_risk_summary_view,
    )

    empty = tmp_path / "empty"
    empty.mkdir()
    for view in (evidence_package_view, release_risk_summary_view, readiness_report_view):
        v = view(runtime_dir=empty)
        assert v["status"] == "not_run"
        assert v["productionReady"] is False
