"""Stage 52 -- audit decision types + notification denylist."""

from __future__ import annotations

from shared.sdk.operator_actions.audit_events import (
    OPERATOR_ACTION_DECISION_TYPES,
    safe_operator_action_refs,
)
from shared.sdk.operator_actions.events import (
    OPERATOR_ACTION_DENY_PATTERNS,
    OPERATOR_ACTION_EVENTS,
)
from shared.sdk.notifications.real_delivery_policy import (
    DEFAULT_REAL_DELIVERY_DENYLIST,
    RealDeliveryPolicy,
    classify_real_delivery,
)


def test_decision_types() -> None:
    assert len(OPERATOR_ACTION_DECISION_TYPES) == 14
    assert "delivery_package_operator_accepted" in OPERATOR_ACTION_DECISION_TYPES
    assert "verification_rerun_completed" in OPERATOR_ACTION_DECISION_TYPES


def test_events() -> None:
    assert "operator_review.accepted" in OPERATOR_ACTION_EVENTS
    assert "verification_rerun.started" in OPERATOR_ACTION_EVENTS


def test_namespaces_default_denied() -> None:
    for pat in OPERATOR_ACTION_DENY_PATTERNS:
        assert pat in DEFAULT_REAL_DELIVERY_DENYLIST


def test_operator_event_blocked_for_real_delivery() -> None:
    policy = RealDeliveryPolicy(
        real_mode_enabled=True,
        denylist=list(DEFAULT_REAL_DELIVERY_DENYLIST),
        test_channel_id="123",
    )
    d = classify_real_delivery(
        {"event_type": "operator_review.accepted", "production_executed": False}, policy
    )
    assert d.decision == "real_blocked"
    assert d.external_sent is False


def test_safe_refs_no_secret_or_prod() -> None:
    refs = safe_operator_action_refs(
        action_type="delivery_package.accept",
        identity_key="operator-test",
        role="operator",
    )
    assert refs["production_executed"] is False
    assert refs["github_write_performed"] is False
    assert refs["deployment_performed"] is False
    assert "password" not in str(refs).lower()
