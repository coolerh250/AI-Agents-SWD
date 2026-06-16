"""Stage 51 -- backup / DR audit decision_type constants + safe refs."""

from __future__ import annotations

DECISION_BACKUP_ENCRYPTION_CONFIGURED = "backup_encryption_configured"
DECISION_BACKUP_RUN_COMPLETED = "backup_run_completed"
DECISION_BACKUP_OFFHOST_TRANSFER_VERIFIED = "backup_offhost_transfer_verified"
DECISION_BACKUP_RESTORE_DRILL_COMPLETED = "backup_restore_drill_completed"
DECISION_BACKUP_SCHEDULE_VALIDATED = "backup_schedule_validated"
DECISION_BACKUP_RETENTION_DRY_RUN_COMPLETED = "backup_retention_dry_run_completed"
DECISION_MIGRATION_ROLLBACK_CATALOG_COMPLETED = "migration_rollback_catalog_completed"
DECISION_BACKUP_READINESS_EVALUATED = "backup_readiness_evaluated"
DECISION_BACKUP_DR_GAP_CLOSURE_FAILED = "backup_dr_gap_closure_failed"

BACKUP_DR_DECISION_TYPES: tuple[str, ...] = (
    DECISION_BACKUP_ENCRYPTION_CONFIGURED,
    DECISION_BACKUP_RUN_COMPLETED,
    DECISION_BACKUP_OFFHOST_TRANSFER_VERIFIED,
    DECISION_BACKUP_RESTORE_DRILL_COMPLETED,
    DECISION_BACKUP_SCHEDULE_VALIDATED,
    DECISION_BACKUP_RETENTION_DRY_RUN_COMPLETED,
    DECISION_MIGRATION_ROLLBACK_CATALOG_COMPLETED,
    DECISION_BACKUP_READINESS_EVALUATED,
    DECISION_BACKUP_DR_GAP_CLOSURE_FAILED,
)


def safe_backup_dr_refs(
    *,
    backup_key: str | None = None,
    environment: str | None = None,
    encryption_key_id: str | None = None,
    encryption_algorithm: str | None = None,
    offhost_target_type: str | None = None,
    restore_key: str | None = None,
    restore_status: str | None = None,
    rto_seconds: float | None = None,
    schedule_key: str | None = None,
    readiness_status: str | None = None,
    remaining_gaps: list[str] | None = None,
    unknown_migration_count: int | None = None,
) -> dict:
    """Audit ``artifact_refs`` carrying only opaque ids / labels / counts /
    statuses -- never a raw key, secret, DB password, or chain-of-thought."""
    refs: dict = {
        "controlled_only": True,
        "production_executed": False,
        "production_backup_performed": False,
        "production_restore_performed": False,
        "real_cloud_write_performed": False,
        "production_schedule_enabled": False,
        "raw_key_persisted": False,
    }
    for key, value in (
        ("backup_key", backup_key),
        ("environment", environment),
        ("encryption_key_id", encryption_key_id),
        ("encryption_algorithm", encryption_algorithm),
        ("offhost_target_type", offhost_target_type),
        ("restore_key", restore_key),
        ("restore_status", restore_status),
        ("schedule_key", schedule_key),
        ("readiness_status", readiness_status),
    ):
        if value is not None:
            refs[key] = value
    if rto_seconds is not None:
        refs["rto_seconds"] = float(rto_seconds)
    if remaining_gaps is not None:
        refs["remaining_gaps"] = list(remaining_gaps)
    if unknown_migration_count is not None:
        refs["unknown_migration_count"] = int(unknown_migration_count)
    return refs


__all__ = [
    "DECISION_BACKUP_ENCRYPTION_CONFIGURED",
    "DECISION_BACKUP_RUN_COMPLETED",
    "DECISION_BACKUP_OFFHOST_TRANSFER_VERIFIED",
    "DECISION_BACKUP_RESTORE_DRILL_COMPLETED",
    "DECISION_BACKUP_SCHEDULE_VALIDATED",
    "DECISION_BACKUP_RETENTION_DRY_RUN_COMPLETED",
    "DECISION_MIGRATION_ROLLBACK_CATALOG_COMPLETED",
    "DECISION_BACKUP_READINESS_EVALUATED",
    "DECISION_BACKUP_DR_GAP_CLOSURE_FAILED",
    "BACKUP_DR_DECISION_TYPES",
    "safe_backup_dr_refs",
]
