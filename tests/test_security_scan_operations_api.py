"""Step 54.2 -- security scan operations API surface (router introspection)."""

from __future__ import annotations

import security_posture_api as sp

EXPECTED = {
    "/operations/security/scans/status",
    "/operations/security/scans/capabilities",
    "/operations/security/scans/targets",
    "/operations/security/scans/exclusions",
    "/operations/security/scans/secret",
    "/operations/security/scans/sast",
    "/operations/security/scans/dependencies",
    "/operations/security/scans/summary",
    "/operations/security/scans/readiness",
}


def test_expected_scan_endpoints_present() -> None:
    paths = {getattr(r, "path", "") for r in sp.router.routes}
    assert EXPECTED <= paths


def test_status_view_not_production_ready() -> None:
    from shared.sdk.security_findings import status_view

    v = status_view()
    assert v["productionReady"] is False
    assert "baselineConfiguration" in v


def test_summary_view_degrades_to_not_run(tmp_path) -> None:
    from shared.sdk.security_findings import summary_view

    v = summary_view(runtime_dir=tmp_path)  # empty dir -> no runtime summary
    assert v["status"] == "not_run"
    assert v["productionReady"] is False
