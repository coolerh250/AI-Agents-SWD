"""Step 62 -- production readiness gate policy."""

from __future__ import annotations

from shared.sdk.production_readiness import policy


def test_dangerous_toggles_false() -> None:
    p = policy.load_policy()
    assert p.get("enabled") is True
    for key in (
        "productionReady",
        "allowProductionDeploy",
        "allowProductionSync",
        "allowProductionRestore",
        "allowProductionFailover",
        "allowAutoPromotion",
        "allowGitHubMerge",
        "allowImagePush",
        "allowRegistryLogin",
        "currentStageAllowsProductionAction",
    ):
        assert p.get(key, False) is False, key


def test_required_guards_true() -> None:
    p = policy.load_policy()
    assert p.get("requireHumanApprovalBeforeProduction") is True
    assert p.get("requireExplicitProductionRolloutPhase") is True


def test_no_production_action_this_stage() -> None:
    assert policy.allows_production_action() is False
