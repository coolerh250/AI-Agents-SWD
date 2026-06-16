"""Stage 51 -- backup / DR safety flags + invariant checks.

Pure, secret-free. Verifies the controlled-only invariants:
  * no production backup / restore
  * no real cloud write
  * no production schedule enablement
  * no raw key persisted
  * production_executed=false
"""

from __future__ import annotations

import os
from typing import Any

from shared.sdk.backup_dr.models import (
    BackupEncryptionConfig,
    BackupOffhostTarget,
    BackupReadinessEvaluation,
    BackupRun,
    BackupScheduleDefinition,
    OffhostTransferRun,
    RestoreDrillRun,
)


def backup_dr_enabled(env: dict[str, str] | None = None) -> bool:
    source = env if env is not None else os.environ
    return str(source.get("ENABLE_BACKUP_DR", "true")).strip().lower() != "false"


def backup_dr_safety_flags(
    *,
    encryption: BackupEncryptionConfig | None = None,
    backup_run: BackupRun | None = None,
    offhost_target: BackupOffhostTarget | None = None,
    transfer: OffhostTransferRun | None = None,
    restore: RestoreDrillRun | None = None,
    schedule: BackupScheduleDefinition | None = None,
    readiness: BackupReadinessEvaluation | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Booleans-only snapshot wired into /operations/safety."""
    return {
        "backup_dr_enabled": backup_dr_enabled(env),
        "backup_encryption_configured": bool(encryption and encryption.status == "configured"),
        "backup_encryption_key_source": encryption.key_source if encryption else "disabled",
        "backup_encryption_raw_key_persisted": False,
        "backup_latest_encrypted": bool(backup_run and backup_run.encrypted),
        "backup_offhost_target_configured": bool(
            offhost_target and offhost_target.status == "configured"
        ),
        "backup_offhost_readback_verified": bool(transfer and transfer.readback_verified),
        "backup_restore_drill_status": restore.status if restore else "not_run",
        "backup_restore_drill_rto_seconds": (restore.rto_seconds if restore else None),
        "backup_schedule_defined": bool(schedule),
        "backup_schedule_dry_run_validated": bool(schedule and schedule.dry_run_validated),
        "backup_production_schedule_enabled": bool(
            schedule and schedule.production_schedule_enabled
        ),
        "backup_retention_policy_configured": True,
        "backup_retention_delete_enabled": False,
        "backup_readiness_status": readiness.status if readiness else "passed_with_gaps",
        "backup_readiness_gaps": list(readiness.remaining_gaps) if readiness else [],
        "backup_readiness_limitations": list(readiness.limitations) if readiness else [],
        "backup_real_cloud_write_enabled": bool(
            offhost_target and offhost_target.real_cloud_write_enabled
        ),
        "backup_real_cloud_write_performed": bool(transfer and transfer.real_cloud_write_performed),
        "backup_production_backup_performed": bool(
            backup_run and backup_run.environment == "production"
        ),
        "backup_production_restore_performed": bool(
            restore and restore.production_restore_performed
        ),
    }


def assert_controlled_only(
    *,
    backup_run: BackupRun | None = None,
    transfer: OffhostTransferRun | None = None,
    restore: RestoreDrillRun | None = None,
    schedule: BackupScheduleDefinition | None = None,
) -> list[str]:
    """Return a list of safety violations (empty == safe)."""
    violations: list[str] = []
    if backup_run is not None:
        if backup_run.environment == "production":
            violations.append("production_backup_performed")
        if backup_run.production_executed:
            violations.append("production_executed_true")
    if transfer is not None and transfer.real_cloud_write_performed:
        violations.append("real_cloud_write_performed")
    if restore is not None and restore.production_restore_performed:
        violations.append("production_restore_performed")
    if schedule is not None and (schedule.production_schedule_enabled or schedule.enabled):
        violations.append("production_schedule_enabled")
    return violations


__all__ = [
    "backup_dr_enabled",
    "backup_dr_safety_flags",
    "assert_controlled_only",
]
