"""Step 63A -- controlled rollout safety fields."""

from __future__ import annotations

from shared.sdk.controlled_rollout import controlled_rollout_safety_fields


def test_enabled_flags() -> None:
    sf = controlled_rollout_safety_fields()
    assert sf["controlled_rollout_review_enabled"] is True
    assert sf["controlled_rollout_review_report_generated"] is True
    assert sf["controlled_rollout_operator_review_enabled"] is True


def test_dangerous_toggles_false() -> None:
    sf = controlled_rollout_safety_fields()
    for k in (
        "controlled_rollout_recommendation_is_approval",
        "controlled_rollout_allows_production_action",
        "controlled_rollout_allows_deploy",
        "controlled_rollout_allows_sync",
        "controlled_rollout_allows_merge",
        "controlled_rollout_allows_image_push",
        "controlled_rollout_allows_restore",
        "controlled_rollout_allows_failover",
        "controlled_rollout_operator_review_is_approval",
    ):
        assert sf[k] is False, k


def test_recommendation_and_counts() -> None:
    sf = controlled_rollout_safety_fields()
    assert sf["controlled_rollout_recommendation"] == "no_go"
    assert sf["controlled_rollout_production_action_executed_count"] == 0
    assert sf["controlled_rollout_missing_target_count"] == 9
