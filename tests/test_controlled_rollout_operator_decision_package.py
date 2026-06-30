"""Step 63A -- controlled rollout operator decision package."""

from __future__ import annotations

from shared.sdk.controlled_rollout import build_operator_decision_package


def test_not_approval_not_ready() -> None:
    pkg = build_operator_decision_package()
    assert pkg["production_ready"] is False
    assert pkg["production_approval"] is False
    assert pkg["production_action_allowed"] is False
    assert pkg["summary"]["recommendation_is_approval"] is False


def test_sections_present() -> None:
    pkg = build_operator_decision_package()
    for sec in (
        "go_no_go_criteria",
        "production_target_assessment",
        "credential_readiness",
        "gitops_readiness",
        "approval_channel_readiness",
        "rollback_dr_readiness",
        "pilot_scope",
        "risk_register",
        "missing_items",
        "recommendation",
    ):
        assert sec in pkg


def test_token_redacted() -> None:
    pkg = build_operator_decision_package(readiness_gate_result={"decision": "x", "token": "abc"})
    assert pkg["readiness_gate_result"]["token"] == "[redacted]"
