"""Step 63A -- controlled rollout go/no-go criteria."""

from __future__ import annotations

from shared.sdk.controlled_rollout import loaders


def test_outcomes() -> None:
    c = loaders.load("criteria")
    assert set(c.get("outcomes", [])) == {"go", "conditional_go", "no_go"}


def test_hard_production_criteria_present() -> None:
    names = {x["name"] for x in loaders.load("criteria").get("criteria", [])}
    for required in (
        "production_target_identified",
        "production_credentials_configured",
        "production_gitops_app_defined",
        "production_approval_channel_defined",
        "operator_owner_assigned",
    ):
        assert required in names


def test_each_criterion_has_status_and_hard() -> None:
    for c in loaders.load("criteria").get("criteria", []):
        assert "status" in c and "hard" in c
