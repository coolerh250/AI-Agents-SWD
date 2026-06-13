"""Stage 41 -- verification.* events must be in the DEFAULT_REAL_DELIVERY_DENYLIST."""

import pytest

from shared.sdk.notifications.real_delivery_policy import (
    DEFAULT_REAL_DELIVERY_DENYLIST,
    RealDeliveryPolicy,
    _matches_pattern,
)
from shared.sdk.verification.audit_events import (
    EVENT_FULL_REGRESSION_FAILED,
    EVENT_FULL_REGRESSION_PASS_WITH_GAPS,
    EVENT_FULL_REGRESSION_PASSED,
    EVENT_VERIFICATION_ENVIRONMENT_FAILED,
    EVENT_VERIFICATION_ENVIRONMENT_READY,
)


def test_verification_wildcard_in_denylist():
    assert any("verification" in p for p in DEFAULT_REAL_DELIVERY_DENYLIST), (
        "verification.* pattern must be in DEFAULT_REAL_DELIVERY_DENYLIST"
    )


@pytest.mark.parametrize(
    "event",
    [
        EVENT_VERIFICATION_ENVIRONMENT_READY,
        EVENT_VERIFICATION_ENVIRONMENT_FAILED,
        EVENT_FULL_REGRESSION_PASSED,
        EVENT_FULL_REGRESSION_FAILED,
        EVENT_FULL_REGRESSION_PASS_WITH_GAPS,
        "verification.environment_ready",
        "verification.full_regression_passed",
        "verification.full_regression_failed",
    ],
)
def test_verification_events_matched_by_denylist(event: str):
    matched = any(
        _matches_pattern(event, pat) for pat in DEFAULT_REAL_DELIVERY_DENYLIST
    )
    assert matched, f"event '{event}' must be blocked by denylist but is not"


def test_verification_events_blocked_by_policy():
    from shared.sdk.notifications.real_delivery_policy import classify_real_delivery

    policy = RealDeliveryPolicy(
        real_mode_enabled=True,
        allowlist=["*"],
        denylist=list(DEFAULT_REAL_DELIVERY_DENYLIST),
        test_channel_id="test-channel",
    )
    for event in [
        EVENT_FULL_REGRESSION_PASSED,
        EVENT_FULL_REGRESSION_FAILED,
        EVENT_VERIFICATION_ENVIRONMENT_READY,
    ]:
        payload = {
            "event_type": event,
            "real_delivery": True,
            "production_executed": False,
            "target_channel": "test-channel",
        }
        decision = classify_real_delivery(payload, policy)
        assert decision.decision != "real_allowed", (
            f"verification event '{event}' must not be real_allowed, got {decision.decision!r}"
        )


def test_verification_not_in_incident_or_backup():
    for pattern in DEFAULT_REAL_DELIVERY_DENYLIST:
        if "verification" in pattern:
            assert not pattern.startswith("incident"), "verification must be its own entry"
            assert not pattern.startswith("backup"), "verification must be its own entry"
