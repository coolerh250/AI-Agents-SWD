"""Stage 51 -- audit decision types + notification denylist."""

from __future__ import annotations

from shared.sdk.backup_dr.audit_events import (
    BACKUP_DR_DECISION_TYPES,
    safe_backup_dr_refs,
)
from shared.sdk.backup_dr.events import (
    BACKUP_DR_EVENTS,
    BACKUP_DR_NOTIFICATION_DENY_PATTERNS,
)
from shared.sdk.notifications.real_delivery_policy import (
    DEFAULT_REAL_DELIVERY_DENYLIST,
    RealDeliveryPolicy,
    classify_real_delivery,
)


def test_decision_types_present() -> None:
    assert "backup_run_completed" in BACKUP_DR_DECISION_TYPES
    assert "backup_readiness_evaluated" in BACKUP_DR_DECISION_TYPES
    assert "migration_rollback_catalog_completed" in BACKUP_DR_DECISION_TYPES
    assert len(BACKUP_DR_DECISION_TYPES) == 9


def test_events_present() -> None:
    assert "backup_dr.readiness_evaluated" in BACKUP_DR_EVENTS
    assert "backup_dr.backup_completed" in BACKUP_DR_EVENTS


def test_namespaces_default_denied() -> None:
    for pat in BACKUP_DR_NOTIFICATION_DENY_PATTERNS:
        assert pat in DEFAULT_REAL_DELIVERY_DENYLIST


def test_backup_dr_event_blocked_for_real_delivery() -> None:
    policy = RealDeliveryPolicy(
        real_mode_enabled=True,
        denylist=list(DEFAULT_REAL_DELIVERY_DENYLIST),
        test_channel_id="123",
    )
    decision = classify_real_delivery(
        {"event_type": "backup_dr.readiness_evaluated", "production_executed": False}, policy
    )
    assert decision.decision == "real_blocked"
    assert decision.external_sent is False


def test_safe_refs_no_secret() -> None:
    refs = safe_backup_dr_refs(
        backup_key="b",
        encryption_key_id="abc",
        readiness_status="passed",
    )
    blob = str(refs).lower()
    assert "password" not in blob
    assert refs["production_executed"] is False
    assert refs["raw_key_persisted"] is False
    assert refs["real_cloud_write_performed"] is False
