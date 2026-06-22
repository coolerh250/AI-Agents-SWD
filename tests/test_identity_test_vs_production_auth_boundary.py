"""Step 52.1 -- test vs production auth boundary + live auth.py fail-closed."""

from __future__ import annotations

from pathlib import Path

import yaml

from shared.sdk.operator_actions.auth import resolve_auth_config

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "identity" / "auth-boundary-policy.yaml"


def _d() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8"))


def test_test_local_dev_test_only() -> None:
    t = _d()["testLocalSignedSession"]
    assert t["environmentsAllowed"] == ["dev", "test"]
    assert t["forbiddenIn"] == ["staging", "production"]
    assert t["grantsDeployOrSync"] is False


def test_production_auth_disabled() -> None:
    p = _d()["productionAuth"]
    assert p["status"] == "disabled"
    assert p["oidcProviderConfigured"] is False


def test_fail_closed_rules_present() -> None:
    keys = {r["key"] for r in _d()["productionFailClosedRules"]}
    assert "production_must_not_use_test_local" in keys
    assert "production_must_not_auto_grant_platform_admin" in keys


def test_live_auth_fail_closed_unknown_mode() -> None:
    cfg = resolve_auth_config({"ADMIN_CONSOLE_AUTH_MODE": "bogus"})
    assert cfg.auth_mode == "disabled"
    assert cfg.operator_actions_enabled is False


def test_live_auth_production_mode_no_operator_actions() -> None:
    cfg = resolve_auth_config(
        {
            "ADMIN_CONSOLE_AUTH_MODE": "oidc",
            "ADMIN_CONSOLE_PRODUCTION_AUTH_ENABLED": "true",
            "ENABLE_ADMIN_CONSOLE_OPERATOR_ACTIONS": "true",
        }
    )
    assert cfg.operator_actions_enabled is False
