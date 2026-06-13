"""Stage 44 -- serialization notification events are denylisted."""

from __future__ import annotations

from shared.sdk.audit_integrity.audit_events import (
    DECISION_AUDIT_TOUCHING_REGRESSION_SERIALIZED,
    DECISION_AUDIT_VERIFICATION_LOCK_ACQUIRED,
    EVENT_AUDIT_TAMPER_RESIDUE_DETECTED,
    EVENT_AUDIT_TAMPER_SIMULATION_RESTORED,
    EVENT_AUDIT_VERIFICATION_LOCK_TIMEOUT,
    EVENT_VERIFICATION_AUDIT_TOUCHING_SERIALIZED,
    STAGE_44_DECISION_TYPES,
    STAGE_44_NOTIFICATION_EVENTS,
)
from shared.sdk.notifications.real_delivery_policy import (
    DEFAULT_REAL_DELIVERY_DENYLIST,
    RealDeliveryPolicy,
    _matches_pattern,
    classify_real_delivery,
)


def test_decision_types_complete_unique():
    assert len(STAGE_44_DECISION_TYPES) == 8
    assert len(set(STAGE_44_DECISION_TYPES)) == 8
    assert DECISION_AUDIT_VERIFICATION_LOCK_ACQUIRED in STAGE_44_DECISION_TYPES
    assert DECISION_AUDIT_TOUCHING_REGRESSION_SERIALIZED in STAGE_44_DECISION_TYPES


def test_notification_events_namespaces():
    assert len(STAGE_44_NOTIFICATION_EVENTS) == 4
    for event in STAGE_44_NOTIFICATION_EVENTS:
        assert event.startswith("audit.") or event.startswith("verification."), event


def test_events_blocked_by_denylist():
    for event in STAGE_44_NOTIFICATION_EVENTS:
        matched = any(_matches_pattern(event, pat) for pat in DEFAULT_REAL_DELIVERY_DENYLIST)
        assert matched, f"{event} must be denylisted"


def test_events_not_real_allowed():
    policy = RealDeliveryPolicy(
        real_mode_enabled=True,
        allowlist=["*"],
        denylist=list(DEFAULT_REAL_DELIVERY_DENYLIST),
        test_channel_id="test-channel",
    )
    for event in [
        EVENT_AUDIT_VERIFICATION_LOCK_TIMEOUT,
        EVENT_AUDIT_TAMPER_RESIDUE_DETECTED,
        EVENT_AUDIT_TAMPER_SIMULATION_RESTORED,
        EVENT_VERIFICATION_AUDIT_TOUCHING_SERIALIZED,
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
