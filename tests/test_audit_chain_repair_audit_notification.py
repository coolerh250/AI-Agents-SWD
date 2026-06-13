"""Stage 42 -- forensic/repair audit decision types + notification events."""

from __future__ import annotations

from shared.sdk.audit_integrity.audit_events import (
    DECISION_AUDIT_CHAIN_FORENSICS_COMPLETED,
    DECISION_AUDIT_CHAIN_REPAIR_COMPLETED,
    DECISION_AUDIT_CHAIN_REPAIR_SKIPPED_UNSAFE,
    EVENT_AUDIT_FORENSICS_COMPLETED,
    EVENT_AUDIT_REPAIR_COMPLETED,
    EVENT_AUDIT_REPAIR_SKIPPED_UNSAFE,
    STAGE_42_DECISION_TYPES,
    STAGE_42_NOTIFICATION_EVENTS,
)
from shared.sdk.notifications.real_delivery_policy import (
    DEFAULT_REAL_DELIVERY_DENYLIST,
    RealDeliveryPolicy,
    _matches_pattern,
    classify_real_delivery,
)


def test_decision_types_complete_and_unique():
    assert len(STAGE_42_DECISION_TYPES) == 9
    assert len(set(STAGE_42_DECISION_TYPES)) == 9
    assert DECISION_AUDIT_CHAIN_FORENSICS_COMPLETED in STAGE_42_DECISION_TYPES
    assert DECISION_AUDIT_CHAIN_REPAIR_COMPLETED in STAGE_42_DECISION_TYPES
    assert DECISION_AUDIT_CHAIN_REPAIR_SKIPPED_UNSAFE in STAGE_42_DECISION_TYPES


def test_notification_events_in_audit_namespace():
    assert len(STAGE_42_NOTIFICATION_EVENTS) == 6
    for event in STAGE_42_NOTIFICATION_EVENTS:
        assert event.startswith("audit."), f"{event} must be in the audit.* namespace"


def test_notification_events_blocked_by_denylist():
    for event in STAGE_42_NOTIFICATION_EVENTS:
        matched = any(_matches_pattern(event, pat) for pat in DEFAULT_REAL_DELIVERY_DENYLIST)
        assert matched, f"{event} must be blocked by the default denylist"


def test_repair_events_not_real_allowed():
    policy = RealDeliveryPolicy(
        real_mode_enabled=True,
        allowlist=["*"],
        denylist=list(DEFAULT_REAL_DELIVERY_DENYLIST),
        test_channel_id="test-channel",
    )
    for event in [
        EVENT_AUDIT_FORENSICS_COMPLETED,
        EVENT_AUDIT_REPAIR_COMPLETED,
        EVENT_AUDIT_REPAIR_SKIPPED_UNSAFE,
    ]:
        payload = {
            "event_type": event,
            "real_delivery": True,
            "production_executed": False,
            "target_channel": "test-channel",
        }
        decision = classify_real_delivery(payload, policy)
        assert decision.decision != "real_allowed"


def test_decision_types_are_snake_case_audit_chain():
    for d in STAGE_42_DECISION_TYPES:
        assert d.startswith("audit_chain_")
