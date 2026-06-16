"""Stage 51 -- backup / DR Redis event constants.

These events are operator-internal and are denied real external delivery by
default (see shared.sdk.notifications.real_delivery_policy -- ``backup_dr.*`` /
``backup.*`` / ``restore.*`` / ``dr.*`` are on the default denylist).
"""

from __future__ import annotations

STREAM_BACKUP_DR = "stream.backup_dr"
STREAM_BACKUP_DR_EVENTS = "stream.backup_dr_events"

EVENT_ENCRYPTION_CONFIGURED = "backup_dr.encryption_configured"
EVENT_BACKUP_STARTED = "backup_dr.backup_started"
EVENT_BACKUP_COMPLETED = "backup_dr.backup_completed"
EVENT_OFFHOST_TRANSFER_VERIFIED = "backup_dr.offhost_transfer_verified"
EVENT_RESTORE_DRILL_COMPLETED = "backup_dr.restore_drill_completed"
EVENT_SCHEDULE_VALIDATED = "backup_dr.schedule_validated"
EVENT_RETENTION_DRY_RUN_COMPLETED = "backup_dr.retention_dry_run_completed"
EVENT_MIGRATION_CATALOG_COMPLETED = "backup_dr.migration_catalog_completed"
EVENT_READINESS_EVALUATED = "backup_dr.readiness_evaluated"
EVENT_FAILED = "backup_dr.failed"

BACKUP_DR_EVENTS: tuple[str, ...] = (
    EVENT_ENCRYPTION_CONFIGURED,
    EVENT_BACKUP_STARTED,
    EVENT_BACKUP_COMPLETED,
    EVENT_OFFHOST_TRANSFER_VERIFIED,
    EVENT_RESTORE_DRILL_COMPLETED,
    EVENT_SCHEDULE_VALIDATED,
    EVENT_RETENTION_DRY_RUN_COMPLETED,
    EVENT_MIGRATION_CATALOG_COMPLETED,
    EVENT_READINESS_EVALUATED,
    EVENT_FAILED,
)

# Notification namespaces that must remain default-denied for real delivery.
BACKUP_DR_NOTIFICATION_DENY_PATTERNS: tuple[str, ...] = (
    "backup_dr.*",
    "backup.*",
    "restore.*",
    "dr.*",
)


__all__ = [
    "STREAM_BACKUP_DR",
    "STREAM_BACKUP_DR_EVENTS",
    "EVENT_ENCRYPTION_CONFIGURED",
    "EVENT_BACKUP_STARTED",
    "EVENT_BACKUP_COMPLETED",
    "EVENT_OFFHOST_TRANSFER_VERIFIED",
    "EVENT_RESTORE_DRILL_COMPLETED",
    "EVENT_SCHEDULE_VALIDATED",
    "EVENT_RETENTION_DRY_RUN_COMPLETED",
    "EVENT_MIGRATION_CATALOG_COMPLETED",
    "EVENT_READINESS_EVALUATED",
    "EVENT_FAILED",
    "BACKUP_DR_EVENTS",
    "BACKUP_DR_NOTIFICATION_DENY_PATTERNS",
]
