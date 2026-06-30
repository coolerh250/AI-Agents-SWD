"""Step 63A -- controlled rollout review policy."""

from __future__ import annotations

from shared.sdk.controlled_rollout import loaders


def test_dangerous_toggles_false() -> None:
    p = loaders.load("policy")
    assert p.get("enabled") is True
    for key in (
        "productionReady",
        "allowsProductionAction",
        "allowsProductionDeploy",
        "allowsProductionSync",
        "allowsProductionRestore",
        "allowsProductionFailover",
        "operatorReviewIsApproval",
        "goRecommendationIsApproval",
        "conditionalGoIsApproval",
    ):
        assert p.get(key, False) is False, key


def test_required_guards_true() -> None:
    p = loaders.load("policy")
    assert p.get("requiresExplicitOperatorApprovalForPilot") is True
    assert p.get("requiresSeparatePilotExecutionStage") is True
    assert p.get("allowsOperatorReviewRequest") is True
