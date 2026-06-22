"""Step 53 -- read-only secret operations API (router-level)."""

from __future__ import annotations

import secret_posture_api as sp

EXPECTED_PATHS = {
    "/operations/secrets/foundation",
    "/operations/secrets/inventory",
    "/operations/secrets/classification",
    "/operations/secrets/ownership",
    "/operations/secrets/references",
    "/operations/secrets/lifecycle",
    "/operations/secrets/rotation",
    "/operations/secrets/access-boundary",
    "/operations/secrets/audit-model",
    "/operations/secrets/redaction",
    "/operations/secrets/usage",
    "/operations/secrets/readiness",
    "/operations/secrets/report",
}


def test_thirteen_get_endpoints() -> None:
    paths = {getattr(r, "path", None) for r in sp.router.routes}
    assert paths == EXPECTED_PATHS


def test_foundation_modeled_fail_closed() -> None:
    d = sp.secrets_foundation()
    assert d["status"] == "modeled_fail_closed_not_configured"
    assert d["productionReady"] is False


def test_readiness_not_production_ready() -> None:
    d = sp.secrets_readiness()
    assert d["productionReady"] is False
    assert d["productionStoreConfigured"] is False


def test_report_sections_present_and_redacted() -> None:
    d = sp.secrets_report()
    for k in ("inventory", "classification", "ownership", "references", "rotation", "redaction"):
        assert k in d
    assert d["productionReady"] is False
