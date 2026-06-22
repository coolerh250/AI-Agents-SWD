"""Step 52.1 -- identity policy catalog."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "identity" / "identity-policy-catalog.yaml"

REQUIRED = {
    "production_auth_must_not_use_test_local",
    "frontend_cannot_authorize_roles",
    "platform_admin_is_not_infrastructure_admin",
    "human_acceptance_is_not_deployment",
    "no_raw_session_token_persistence",
    "no_oidc_secret_in_repo",
}


def _keys() -> set[str]:
    return {p["key"] for p in yaml.safe_load(F.read_text(encoding="utf-8"))["policies"]}


def test_required_policies_present() -> None:
    assert REQUIRED <= _keys()


def test_each_policy_has_rule_and_severity() -> None:
    for p in yaml.safe_load(F.read_text(encoding="utf-8"))["policies"]:
        assert p.get("rule")
        assert p.get("severity") in ("critical", "high", "medium")
