"""Step 52.3 -- role mapping policy file."""

from __future__ import annotations

from shared.sdk.identity import load_policy


def _rm() -> dict:
    return load_policy()["roleMapping"]


def test_disabled_unconfigured_empty_rules() -> None:
    rm = _rm()
    assert rm["enabled"] is False
    assert rm["configured"] is False
    assert rm["rules"] == []


def test_default_none_unknown_deny_no_frontend_authority() -> None:
    rm = _rm()
    assert rm["defaultRole"] == "none"
    assert rm["unknownUserBehavior"] == "deny"
    assert rm["frontendRoleAuthority"] is False


def test_all_roles_require_explicit_mapping() -> None:
    assert set(_rm()["requiresExplicitMapping"]) == {
        "viewer",
        "reviewer",
        "operator",
        "platform_admin",
    }


def test_forbidden_flags() -> None:
    fb = _rm()["forbidden"]
    assert all(
        fb[k]
        for k in (
            "wildcardGroups",
            "defaultOperator",
            "defaultPlatformAdmin",
            "tokenRoleClaimAuthority",
            "autoProvisionUsers",
        )
    )


def test_not_production_ready() -> None:
    assert load_policy()["status"]["productionReady"] is False
