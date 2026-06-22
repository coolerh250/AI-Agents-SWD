"""Step 52.4 -- production identity is never declared ready; Step 52.1-3 intact."""

from __future__ import annotations

from pathlib import Path

import yaml

from shared.sdk.identity_posture import (
    build_identity_posture_summary,
    full_report,
    readiness_view,
)

ROOT = Path(__file__).resolve().parents[1]
IDENT = ROOT / "infra" / "identity"


def test_readiness_never_production_ready() -> None:
    r = readiness_view(build_identity_posture_summary())
    assert r["productionIdentityReady"] is False
    assert r["productionAuthEnabled"] is False
    assert r["oidcEnabled"] is False
    assert r["blockers"]


def test_report_lists_next_required_steps() -> None:
    r = full_report(build_identity_posture_summary())
    steps = r["nextRequiredSteps"]
    assert any("53" in s for s in steps)  # production secret store
    assert any("60" in s for s in steps)  # production approval identity chain


def test_step_52_1_oidc_prereqs_still_unconfigured() -> None:
    oidc = yaml.safe_load(
        (IDENT / "production-oidc-prerequisites.yaml").read_text(encoding="utf-8")
    )
    prov = oidc["oidcPrerequisites"]["provider"]
    assert all(prov[k]["configured"] is False for k in ("issuerUrl", "jwksUri", "clientId"))


def test_step_52_2_provider_disabled() -> None:
    cat = yaml.safe_load((IDENT / "oidc-provider-catalog.yaml").read_text(encoding="utf-8"))
    prov = cat["providers"]["production-oidc-placeholder"]
    assert prov["enabled"] is False
    assert prov["status"] == "disabled_unconfigured"


def test_step_52_3_role_mapping_unconfigured_breakglass_disabled() -> None:
    rm = yaml.safe_load((IDENT / "role-mapping-policy.yaml").read_text(encoding="utf-8"))[
        "roleMapping"
    ]
    assert rm["configured"] is False and rm["defaultRole"] == "none"
    bg = yaml.safe_load((IDENT / "break-glass-model.yaml").read_text(encoding="utf-8"))[
        "breakGlass"
    ]
    assert bg["enabled"] is False
