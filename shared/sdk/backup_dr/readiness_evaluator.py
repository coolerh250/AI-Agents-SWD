"""Stage 51 -- backup / DR readiness evaluator.

Decides whether the four long-standing gaps are closed and resolves an overall
readiness status. Because this stage does NOT use a real production secret
store, real cloud target, or real production schedule, a fully-closed baseline
resolves to ``passed_with_non_production_limitations`` (never a bare
``passed`` claim of production readiness).
"""

from __future__ import annotations

from shared.sdk.backup_dr.models import (
    BackupEncryptionConfig,
    BackupReadinessEvaluation,
    BackupScheduleDefinition,
    MigrationRollbackCatalogEntry,
    OffhostTransferRun,
    RestoreDrillRun,
)
from shared.sdk.backup_dr.encryption_config import encryption_gap_closed as _enc_closed
from shared.sdk.backup_dr.migration_catalog import migration_down_gap_closed as _mig_closed
from shared.sdk.backup_dr.offhost_transfer import offhost_gap_closed as _off_closed
from shared.sdk.backup_dr.schedule_builder import schedule_gap_closed as _sched_closed

ORIGINAL_GAPS = (
    "encryption_no_key",
    "storage_not_off_host",
    "schedule_dry_run_only",
    "migration_down_gaps",
)

NON_PRODUCTION_LIMITATIONS = (
    "real production secret store not integrated",
    "real off-host cloud target not enabled",
    "production schedule not enabled",
    "production restore not executed",
    "Kubernetes CronJob not applied",
)


def evaluate_readiness(
    *,
    encryption: BackupEncryptionConfig,
    transfer: OffhostTransferRun,
    schedule: BackupScheduleDefinition,
    migration_entries: list[MigrationRollbackCatalogEntry],
    restore: RestoreDrillRun | None = None,
    evaluation_key: str = "backup-dr-readiness",
) -> BackupReadinessEvaluation:
    enc_closed = _enc_closed(encryption)
    off_closed = _off_closed(transfer)
    sched_closed = _sched_closed(schedule)
    mig_closed = _mig_closed(migration_entries)

    remaining: list[str] = []
    if not enc_closed:
        remaining.append("encryption_no_key")
    if not off_closed:
        remaining.append("storage_not_off_host")
    if not sched_closed:
        remaining.append("schedule_dry_run_only")
    if not mig_closed:
        remaining.append("migration_down_gaps")

    all_closed = not remaining
    if all_closed:
        status = "passed_with_non_production_limitations"
        limitations = list(NON_PRODUCTION_LIMITATIONS)
    else:
        status = "passed_with_gaps"
        limitations = list(NON_PRODUCTION_LIMITATIONS)

    metadata = {
        "restore_drill_status": restore.status if restore else "not_run",
        "restore_drill_rto_seconds": restore.rto_seconds if restore else None,
        "production_executed": False,
        "real_cloud_write_performed": False,
        "production_restore_performed": (
            restore.production_restore_performed if restore else False
        ),
    }

    return BackupReadinessEvaluation(
        evaluation_key=evaluation_key,
        status=status,
        encryption_gap_closed=enc_closed,
        offhost_gap_closed=off_closed,
        schedule_gap_closed=sched_closed,
        migration_down_gap_closed=mig_closed,
        remaining_gaps=remaining,
        limitations=limitations,
        metadata=metadata,
    )


__all__ = ["ORIGINAL_GAPS", "NON_PRODUCTION_LIMITATIONS", "evaluate_readiness"]
