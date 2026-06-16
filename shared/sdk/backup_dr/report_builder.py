"""Stage 51 -- Backup / DR gap closure report builder.

Produces a secret-free report aggregating encryption / off-host / restore drill
/ schedule dry-run / retention dry-run / migration rollback catalog results plus
the readiness status, remaining limitations, and safety evidence.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from shared.sdk.backup_dr.models import (
    BackupEncryptionConfig,
    BackupManifest,
    BackupOffhostTarget,
    BackupReadinessEvaluation,
    BackupRun,
    BackupScheduleDefinition,
    MigrationRollbackCatalogEntry,
    OffhostTransferRun,
    RestoreDrillRun,
)
from shared.sdk.backup_dr.migration_catalog import catalog_summary


def build_gap_closure_report(
    *,
    encryption: BackupEncryptionConfig,
    backup_run: BackupRun,
    manifest: BackupManifest,
    offhost_target: BackupOffhostTarget,
    transfer: OffhostTransferRun,
    restore: RestoreDrillRun | None,
    schedule: BackupScheduleDefinition,
    retention_dry_run: dict[str, Any],
    migration_entries: list[MigrationRollbackCatalogEntry],
    readiness: BackupReadinessEvaluation,
) -> dict[str, Any]:
    mig = catalog_summary(migration_entries)
    return {
        "report_version": "1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "controlled_only": True,
        "production_executed": False,
        "encryption": {
            "key_source": encryption.key_source,
            "key_id": encryption.key_id,
            "algorithm": encryption.algorithm,
            "status": encryption.status,
            "raw_key_persisted": False,
        },
        "backup": {
            "backup_key": backup_run.backup_key,
            "environment": backup_run.environment,
            "encrypted": backup_run.encrypted,
            "checksum_sha256": backup_run.checksum_sha256,
            "encrypted_checksum_sha256": backup_run.encrypted_checksum_sha256,
            "manifest_key_id": manifest.encryption_key_id,
        },
        "offhost": {
            "target_type": offhost_target.target_type,
            "target_uri": offhost_target.target_uri,
            "status": transfer.status,
            "readback_verified": transfer.readback_verified,
            "real_cloud_write_enabled": offhost_target.real_cloud_write_enabled,
            "real_cloud_write_performed": transfer.real_cloud_write_performed,
        },
        "restore_drill": {
            "status": restore.status if restore else "not_run",
            "restore_mode": restore.restore_mode if restore else None,
            "target_database": restore.target_database if restore else None,
            "rto_seconds": restore.rto_seconds if restore else None,
            "schema_verified": restore.schema_verified if restore else False,
            "row_count_verified": restore.row_count_verified if restore else False,
            "production_restore_performed": (
                restore.production_restore_performed if restore else False
            ),
        },
        "schedule": {
            "schedule_type": schedule.schedule_type,
            "schedule_expression": schedule.schedule_expression,
            "dry_run_validated": schedule.dry_run_validated,
            "production_schedule_enabled": schedule.production_schedule_enabled,
            "enabled": schedule.enabled,
        },
        "retention": {
            "policy_key": retention_dry_run.get("policy_key"),
            "candidate_delete_count": retention_dry_run.get("candidate_delete_count", 0),
            "actual_delete_count": retention_dry_run.get("actual_delete_count", 0),
            "delete_enabled": retention_dry_run.get("delete_enabled", False),
            "dry_run_only": retention_dry_run.get("dry_run_only", True),
        },
        "migration_rollback_catalog": mig,
        "readiness": {
            "status": readiness.status,
            "encryption_gap_closed": readiness.encryption_gap_closed,
            "offhost_gap_closed": readiness.offhost_gap_closed,
            "schedule_gap_closed": readiness.schedule_gap_closed,
            "migration_down_gap_closed": readiness.migration_down_gap_closed,
            "remaining_gaps": list(readiness.remaining_gaps),
            "limitations": list(readiness.limitations),
        },
        "safety_evidence": {
            "production_backup_performed": False,
            "production_restore_performed": (
                restore.production_restore_performed if restore else False
            ),
            "real_cloud_write_performed": transfer.real_cloud_write_performed,
            "production_schedule_enabled": schedule.production_schedule_enabled,
            "raw_key_persisted": False,
            "production_executed": False,
        },
    }


__all__ = ["build_gap_closure_report"]
