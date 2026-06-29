"""Step 60 -- release governance safety fields posture."""

from __future__ import annotations

from shared.sdk.release_governance import release_governance_safety_fields


def test_safety_fields_production_blocked() -> None:
    f = release_governance_safety_fields()
    assert f["release_governance_enabled"] is True
    assert f["release_candidate_enabled"] is True
    assert f["deployment_intent_enabled"] is True
    for key in (
        "release_governance_production_ready",
        "release_governance_allow_production_deploy",
        "release_governance_allow_auto_promotion",
        "release_governance_allow_github_merge",
        "release_governance_allow_argocd_production_sync",
        "release_governance_allow_image_push",
        "release_governance_allow_registry_login",
    ):
        assert f[key] is False, key
    for key in (
        "release_candidate_production_ready_count",
        "deployment_intent_production_target_count",
        "deployment_intent_production_executed_count",
    ):
        assert f[key] == 0, key


def test_counts_passthrough() -> None:
    f = release_governance_safety_fields(
        release_candidate_production_ready_count=0,
        deployment_intent_production_target_count=0,
        deployment_intent_production_executed_count=0,
    )
    assert f["deployment_intent_production_executed_count"] == 0
