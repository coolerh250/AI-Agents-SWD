"""Stage 31 -- approval-policy metrics counters."""

from __future__ import annotations

from shared.sdk.observability import metrics as M


def test_stage31_metrics_defined() -> None:
    for name in (
        "APPROVAL_POLICIES_TOTAL",
        "APPROVAL_POLICY_ACTIVE_TOTAL",
        "APPROVAL_POLICY_REVOKED_TOTAL",
        "APPROVAL_POLICY_DECISIONS_TOTAL",
        "APPROVAL_POLICY_ACTION_ALLOWED_TOTAL",
        "APPROVAL_POLICY_ACTION_BLOCKED_TOTAL",
        "DELEGATED_ACTIONS_USED_TOTAL",
        "LLM_PROMOTIONS_TOTAL",
    ):
        assert hasattr(M, name), name


def test_approval_policies_total_labels() -> None:
    M.APPROVAL_POLICIES_TOTAL.labels(approval_mode="delegated", scope_type="task").inc()


def test_decisions_total_labels() -> None:
    M.APPROVAL_POLICY_DECISIONS_TOTAL.labels(
        approval_mode="delegated",
        action_type="llm_proposal_promote",
        decision="delegated",
    ).inc()


def test_action_blocked_total_labels() -> None:
    M.APPROVAL_POLICY_ACTION_BLOCKED_TOTAL.labels(
        reason="hard_safety:production_deploy",
        action_type="production_deploy",
    ).inc()


def test_metrics_endpoint_exposes_stage31_counters() -> None:
    body, _ct = M.metrics_response()
    text = body.decode("utf-8")
    for name in (
        "approval_policies_total",
        "approval_policy_decisions_total",
        "approval_policy_action_blocked_total",
        "llm_promotions_total",
        "delegated_actions_used_total",
    ):
        assert name in text, name
