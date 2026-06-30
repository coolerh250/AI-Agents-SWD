"""Step 63A -- controlled rollout pilot scope."""

from __future__ import annotations

from shared.sdk.controlled_rollout import loaders


def test_scope_constraints() -> None:
    constraints = set(loaders.load("scope").get("constraints", []))
    for required in (
        "single_service",
        "single_environment",
        "manual_approval",
        "manual_rollback",
        "no_auto_promotion",
    ):
        assert required in constraints


def test_no_auto_promotion_no_external_traffic() -> None:
    s = loaders.load("scope")
    assert s.get("auto_promotion") is False
    assert s.get("external_customer_traffic") is False


def test_blast_radius_and_rollback_trigger_describable() -> None:
    s = loaders.load("scope")
    assert s.get("blast_radius")
    assert s.get("rollback_trigger")
