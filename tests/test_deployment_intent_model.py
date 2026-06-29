"""Step 60 -- deployment intent builder (never executes a deployment)."""

from __future__ import annotations

from shared.sdk.release_governance import build_intent


def test_validate_only_validated_no_execution() -> None:
    i = build_intent(release_candidate_id="rc", requested_action="validate_only")
    assert i.status == "validated"
    d = i.to_dict()
    assert d["production_executed"] is False
    assert d["deploy_performed"] is False
    assert d["argocd_sync_performed"] is False
    assert d["merge_performed"] is False
    assert d["image_push_performed"] is False


def test_request_operator_review_requires_approval() -> None:
    i = build_intent(release_candidate_id="rc", requested_action="request_operator_review")
    assert i.status == "operator_review_requested"
    assert i.requires_human_approval is True


def test_forbidden_actions_blocked() -> None:
    for action in (
        "deploy_production",
        "sync_production",
        "merge_pr",
        "push_image",
        "create_release",
    ):
        i = build_intent(release_candidate_id="rc", requested_action=action)
        assert i.status == "blocked"
        assert (i.blocked_reason or "").startswith("forbidden_action")


def test_production_target_blocked() -> None:
    i = build_intent(
        release_candidate_id="rc", requested_action="validate_only", target_environment="production"
    )
    assert i.status == "blocked"
    assert i.blocked_reason == "production_environment_forbidden"


def test_unknown_action_blocked() -> None:
    i = build_intent(release_candidate_id="rc", requested_action="do_something")
    assert i.status == "blocked"
    assert (i.blocked_reason or "").startswith("unknown_action")
