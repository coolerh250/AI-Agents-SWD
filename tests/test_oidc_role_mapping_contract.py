"""Step 52.2 -- OIDC role mapping contract: deny unknown, no auto-grant."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "identity" / "oidc-role-mapping-contract.yaml"


def _d() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8"))


def test_mapping_not_configured() -> None:
    rm = _d()["roleMapping"]
    assert rm["configured"] is False
    assert rm["sourceClaim"] == "groups"
    assert rm["rules"] == []


def test_unknown_user_deny_default_none() -> None:
    rm = _d()["roleMapping"]
    assert rm["unknownUserBehavior"] == "deny"
    assert rm["defaultRole"] == "none"


def test_platform_admin_not_auto_granted() -> None:
    d = _d()
    assert "platform_admin" in d["forbiddenAutoGrant"]
    for role in ("reviewer", "operator", "platform_admin"):
        assert role in d["requiresExplicitMapping"]


def test_allowed_roles() -> None:
    assert set(_d()["allowedRoles"]) == {"viewer", "reviewer", "operator", "platform_admin"}
