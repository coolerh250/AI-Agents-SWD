"""Step 52.4 -- read-only identity operations API (router-level)."""

from __future__ import annotations

import identity_posture_api as ip

EXPECTED_PATHS = {
    "/operations/identity/posture",
    "/operations/identity/authentication",
    "/operations/identity/session",
    "/operations/identity/csrf",
    "/operations/identity/rbac",
    "/operations/identity/operator-actions",
    "/operations/identity/oidc",
    "/operations/identity/role-mapping",
    "/operations/identity/break-glass",
    "/operations/identity/audit-mapping",
    "/operations/identity/risks",
    "/operations/identity/readiness",
    "/operations/identity/report",
}


def test_thirteen_get_endpoints() -> None:
    paths = {getattr(r, "path", None) for r in ip.router.routes}
    assert paths == EXPECTED_PATHS


def test_posture_modeled_fail_closed() -> None:
    d = ip.identity_posture()
    assert d["status"] == "modeled_fail_closed_not_enabled"
    assert d["productionIdentityReady"] is False


def test_readiness_not_production_ready() -> None:
    d = ip.identity_readiness()
    assert d["productionIdentityReady"] is False
    assert d["productionAuthEnabled"] is False
    assert d["oidcEnabled"] is False


def test_report_sections_present() -> None:
    d = ip.identity_report()
    for key in ("oidc", "session", "roleMapping", "breakGlass", "authorization"):
        assert key in d
    assert d["productionIdentityReady"] is False
