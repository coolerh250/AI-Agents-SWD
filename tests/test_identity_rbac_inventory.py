"""Step 52.1 -- RBAC inventory + cross-check against live catalog."""

from __future__ import annotations

from pathlib import Path

import yaml

from shared.sdk.operator_actions.action_catalog import ENABLED_ACTIONS
from shared.sdk.operator_actions.rbac import role_can

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "identity" / "rbac-inventory.yaml"
INFRA = {
    "deploy",
    "sync",
    "github_write",
    "pr",
    "argocd_sync",
    "kubernetes_apply",
    "production_backup",
    "production_restore",
    "root",
    "production",
}


def _roles() -> dict:
    return {r["key"]: r for r in yaml.safe_load(F.read_text(encoding="utf-8"))["roles"]}


def test_four_roles() -> None:
    assert set(_roles()) == {"viewer", "reviewer", "operator", "platform_admin"}


def test_viewer_read_only() -> None:
    assert _roles()["viewer"]["permissions"] == []
    for a in ENABLED_ACTIONS:
        assert role_can("viewer", a) is False


def test_platform_admin_no_infra_authority() -> None:
    pa = _roles()["platform_admin"]
    assert pa["productionAuthority"] == "none"
    assert not (INFRA & set(pa["permissions"]))


def test_operator_cannot_deploy_or_github() -> None:
    # no enabled action is a deploy/github action, so operator/platform_admin cannot perform one
    for a in ENABLED_ACTIONS:
        assert not any(s in a for s in ("deploy", "github", "argocd", "kubernetes"))


def test_reviewer_cannot_accept() -> None:
    assert role_can("reviewer", "delivery_package.accept") is False
    assert role_can("reviewer", "operator_review.add_note") is True
