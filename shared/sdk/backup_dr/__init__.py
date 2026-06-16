"""Stage 51 -- Backup / DR Gap Closure SDK (Step 49).

Extends the Stage 36 ``shared.sdk.backup`` primitives (checksum, encryption
metadata, manifest, storage, restore) into a verifiable, auditable,
recoverable, reportable readiness baseline that closes the four long-standing
documented gaps:

  encryption_no_key, storage_not_off_host, schedule_dry_run_only,
  migration_down_gaps.

Controlled / test environment ONLY: no production backup / restore, no real
cloud bucket write, no real production schedule, no raw key persisted. A fully
closed baseline resolves to ``passed_with_non_production_limitations`` -- never
a bare production-ready claim.
"""

from __future__ import annotations

from shared.sdk.backup_dr.audit_events import (
    BACKUP_DR_DECISION_TYPES,
    safe_backup_dr_refs,
)
from shared.sdk.backup_dr.events import (
    BACKUP_DR_EVENTS,
    BACKUP_DR_NOTIFICATION_DENY_PATTERNS,
)
from shared.sdk.backup_dr.models import (
    BackupDrVerificationResult,
    BackupEncryptionConfig,
    BackupManifest,
    BackupOffhostTarget,
    BackupReadinessEvaluation,
    BackupRetentionPolicy,
    BackupRun,
    BackupScheduleDefinition,
    MigrationRollbackCatalogEntry,
    OffhostTransferRun,
    RestoreDrillRun,
)
from shared.sdk.backup_dr.store import DEFAULT_DATABASE_URL, BackupDrStore

__all__ = [
    "BackupEncryptionConfig",
    "BackupRun",
    "BackupManifest",
    "BackupOffhostTarget",
    "OffhostTransferRun",
    "RestoreDrillRun",
    "BackupScheduleDefinition",
    "BackupRetentionPolicy",
    "MigrationRollbackCatalogEntry",
    "BackupReadinessEvaluation",
    "BackupDrVerificationResult",
    "BackupDrStore",
    "DEFAULT_DATABASE_URL",
    "BACKUP_DR_DECISION_TYPES",
    "safe_backup_dr_refs",
    "BACKUP_DR_EVENTS",
    "BACKUP_DR_NOTIFICATION_DENY_PATTERNS",
]
