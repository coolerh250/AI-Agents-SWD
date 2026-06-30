"""Step 63A -- controlled rollout recommendation."""

from __future__ import annotations

from shared.sdk.controlled_rollout import recommendation


def test_no_go_at_this_stage() -> None:
    rec = recommendation.evaluate()
    assert rec["recommendation"] == "no_go"
    assert rec["no_go_reasons"]


def test_recommendation_never_approval() -> None:
    rec = recommendation.evaluate()
    assert rec["recommendation_is_approval"] is False
    assert rec["authorizes_production_action"] is False
    assert rec["production_ready"] is False
    assert rec["production_approved"] is False


def test_missing_counts_nonzero() -> None:
    rec = recommendation.evaluate()
    assert rec["missing_target_count"] == 9
    assert rec["missing_credential_count"] == 5
    assert rec["missing_gitops_count"] == 5
    assert rec["missing_approval_channel_count"] == 4
