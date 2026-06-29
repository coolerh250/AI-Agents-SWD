"""Step 60 -- release governance policy + environment validation."""

from __future__ import annotations

from shared.sdk.release_governance import policy


def test_policy_production_blocked() -> None:
    p = policy.load_policy()
    assert p["enabled"] is True
    assert p["productionReady"] is False
    for key in (
        "allowProductionDeploy",
        "allowAutoPromotion",
        "allowGitHubMerge",
        "allowTagCreation",
        "allowReleaseCreation",
        "allowImagePush",
        "allowRegistryLogin",
        "allowArgoCDProductionSync",
    ):
        assert p[key] is False


def test_environment_validation() -> None:
    assert policy.validate_environment("nonprod") == ("nonprod", None)
    assert policy.validate_environment(None)[0] == "nonprod"
    env, reason = policy.validate_environment("production")
    assert reason == "production_environment_forbidden"
    env, reason = policy.validate_environment("prod")
    assert reason == "production_environment_forbidden"
    _, reason = policy.validate_environment("staging")
    assert reason and reason.startswith("environment_not_allowed")
