"""Stage 43 -- restore audit decision types + notification events."""

from __future__ import annotations

from shared.sdk.audit_integrity.audit_events import (
    DECISION_AUDIT_LOG_RESTORE_COMPLETED,
    DECISION_AUDIT_LOG_RESTORE_PRECHECK_PASSED,
    DECISION_AUDIT_LOG_RESTORE_VERIFIED,
    EVENT_AUDIT_LOG_RESTORE_COMPLETED,
    EVENT_AUDIT_LOG_RESTORE_FAILED,
    EVENT_AUDIT_LOG_RESTORE_VERIFIED,
    STAGE_43_DECISION_TYPES,
    STAGE_43_NOTIFICATION_EVENTS,
)
from shared.sdk.notifications.real_delivery_policy import (
    DEFAULT_REAL_DELIVERY_DENYLIST,
    RealDeliveryPolicy,
    _matches_pattern,
    classify_real_delivery,
)


def test_decision_types_complete_and_unique():
    assert len(STAGE_43_DECISION_TYPES) == 9
    assert len(set(STAGE_43_DECISION_TYPES)) == 9
    assert DECISION_AUDIT_LOG_RESTORE_COMPLETED in STAGE_43_DECISION_TYPES
    assert DECISION_AUDIT_LOG_RESTORE_PRECHECK_PASSED in STAGE_43_DECISION_TYPES
    assert DECISION_AUDIT_LOG_RESTORE_VERIFIED in STAGE_43_DECISION_TYPES


def test_decision_types_snake_case_prefixed():
    for d in STAGE_43_DECISION_TYPES:
        assert d.startswith("audit_log_restore_")


def test_notification_events_in_audit_namespace():
    assert len(STAGE_43_NOTIFICATION_EVENTS) == 4
    for event in STAGE_43_NOTIFICATION_EVENTS:
        assert event.startswith("audit."), event


def test_notification_events_blocked_by_denylist():
    for event in STAGE_43_NOTIFICATION_EVENTS:
        matched = any(_matches_pattern(event, pat) for pat in DEFAULT_REAL_DELIVERY_DENYLIST)
        assert matched, f"{event} must be denylisted"


def test_restore_events_not_real_allowed():
    policy = RealDeliveryPolicy(
        real_mode_enabled=True,
        allowlist=["*"],
        denylist=list(DEFAULT_REAL_DELIVERY_DENYLIST),
        test_channel_id="test-channel",
    )
    for event in [
        EVENT_AUDIT_LOG_RESTORE_COMPLETED,
        EVENT_AUDIT_LOG_RESTORE_FAILED,
        EVENT_AUDIT_LOG_RESTORE_VERIFIED,
    ]:
        decision = classify_real_delivery(
            {
                "event_type": event,
                "real_delivery": True,
                "production_executed": False,
                "target_channel": "test-channel",
            },
            policy,
        )
        assert decision.decision != "real_allowed"
