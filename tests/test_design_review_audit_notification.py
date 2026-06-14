"""Stage 46 -- design review audit decision types + notification denylist."""

from __future__ import annotations

from shared.sdk.agent_discussion.audit_events import AGENT_DISCUSSION_DECISION_TYPES
from shared.sdk.agent_discussion.events import DISCUSSION_NOTIFICATION_EVENTS
from shared.sdk.design_review.audit_events import DESIGN_REVIEW_DECISION_TYPES
from shared.sdk.design_review.events import DESIGN_REVIEW_NOTIFICATION_EVENTS
from shared.sdk.notifications.real_delivery_policy import (
    DEFAULT_REAL_DELIVERY_DENYLIST,
    RealDeliveryPolicy,
    classify_real_delivery,
    _matches_pattern,
)


def test_audit_decision_types_present() -> None:
    for d in (
        "agent_discussion_started",
        "agent_discussion_completed",
        "agent_discussion_contribution_recorded",
    ):
        assert d in AGENT_DISCUSSION_DECISION_TYPES
    for d in (
        "design_review_started",
        "design_review_completed",
        "design_review_finding_created",
        "design_review_gate_evaluated",
        "design_review_go_no_go_recorded",
        "design_review_blocked",
    ):
        assert d in DESIGN_REVIEW_DECISION_TYPES


def test_namespaces_in_denylist() -> None:
    assert "discussion.*" in DEFAULT_REAL_DELIVERY_DENYLIST
    assert "design_review.*" in DEFAULT_REAL_DELIVERY_DENYLIST
    assert "project.*" in DEFAULT_REAL_DELIVERY_DENYLIST
    assert "audit.*" in DEFAULT_REAL_DELIVERY_DENYLIST
    assert "verification.*" in DEFAULT_REAL_DELIVERY_DENYLIST


def test_all_events_denylisted_by_pattern() -> None:
    events = list(DISCUSSION_NOTIFICATION_EVENTS) + list(DESIGN_REVIEW_NOTIFICATION_EVENTS)
    for e in events:
        assert any(_matches_pattern(e, p) for p in DEFAULT_REAL_DELIVERY_DENYLIST), e


def test_events_blocked_even_in_real_mode() -> None:
    policy = RealDeliveryPolicy(
        real_mode_enabled=True,
        allowlist=[],
        denylist=list(DEFAULT_REAL_DELIVERY_DENYLIST),
        test_channel_id="123",
    )
    for e in list(DISCUSSION_NOTIFICATION_EVENTS) + list(DESIGN_REVIEW_NOTIFICATION_EVENTS):
        d = classify_real_delivery({"event_type": e, "production_executed": False}, policy)
        assert d.decision == "real_blocked"
        assert d.external_sent is False
