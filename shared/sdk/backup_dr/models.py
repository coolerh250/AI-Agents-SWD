"""Stage 51 -- Pydantic models for the Backup / DR readiness baseline.

Strict, metadata-only models. No raw key / secret / token / password fields.
``production_executed`` is always false in test mode; real cloud write and real
production schedule are always disabled by default. These models describe the
verifiable, auditable, recoverable, reportable Backup / DR readiness baseline
that closes the four long-standing gaps (encryption_no_key,
storage_not_off_host, schedule_dry_run_only, migration_down_gaps).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

KEY_SOURCES = ("key_file", "mock_vault", "env_reference", "disabled")
ENC_CONFIG_STATUSES = ("configured", "missing", "invalid", "disabled")
BACKUP_ENVIRONMENTS = ("test", "dev", "staging", "production")
BACKUP_RUN_STATUSES = ("started", "completed", "failed", "skipped")
OFFHOST_TARGET_TYPES = ("mock_local_remote", "s3_disabled", "gcs_disabled", "azure_disabled")
OFFHOST_TARGET_STATUSES = ("configured", "unavailable", "disabled")
OFFHOST_TRANSFER_STATUSES = ("started", "copied", "verified", "failed", "skipped")
RESTORE_MODES = ("isolated_test_db", "dry_run", "metadata_only")
RESTORE_STATUSES = ("started", "restored", "verified", "failed", "skipped")
SCHEDULE_TYPES = ("cron_spec", "systemd_timer_spec", "kubernetes_cronjob_spec", "dry_run_only")
RETENTION_DRY_RUN_STATUSES = ("completed", "failed", "skipped")
REVERSIBILITY = ("reversible", "forward_only", "manual_rollback_required", "unknown")
RISK_LEVELS = ("low", "medium", "high", "critical")
READINESS_STATUSES = (
    "passed",
    "passed_with_non_production_limitations",
    "passed_with_gaps",
    "failed",
)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class BackupEncryptionConfig(_Strict):
    config_key: str
    key_source: str = "key_file"
    key_ref: str | None = None
    key_id: str | None = None
    algorithm: str = "openssl-aes-256-cbc"
    status: str = "missing"
    production_usable: bool = False
    test_only: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class BackupRun(_Strict):
    backup_key: str
    environment: str = "test"
    source_database: str
    status: str = "started"
    encrypted: bool = False
    encryption_config_id: str | None = None
    artifact_path: str | None = None
    manifest_path: str | None = None
    checksum_sha256: str | None = None
    encrypted_checksum_sha256: str | None = None
    size_bytes: int | None = None
    production_executed: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class BackupManifest(_Strict):
    backup_run_id: str | None = None
    manifest_version: str = "1"
    source_database: str | None = None
    schema_migration_count: int | None = None
    table_count: int | None = None
    row_count_summary: dict[str, int] = Field(default_factory=dict)
    artifact_checksum_sha256: str | None = None
    encrypted_artifact_checksum_sha256: str | None = None
    encryption_key_id: str | None = None
    encryption_algorithm: str | None = None
    manifest_json: dict[str, Any] = Field(default_factory=dict)


class BackupOffhostTarget(_Strict):
    target_key: str
    target_type: str = "mock_local_remote"
    target_uri: str
    status: str = "configured"
    real_cloud_write_enabled: bool = False
    test_only: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class OffhostTransferRun(_Strict):
    backup_run_id: str | None = None
    target_id: str | None = None
    status: str = "started"
    source_path: str | None = None
    target_path: str | None = None
    source_checksum_sha256: str | None = None
    target_checksum_sha256: str | None = None
    readback_verified: bool = False
    real_cloud_write_performed: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class RestoreDrillRun(_Strict):
    backup_run_id: str | None = None
    restore_key: str
    target_database: str
    restore_mode: str = "isolated_test_db"
    status: str = "started"
    rto_seconds: float | None = None
    row_count_verified: bool = False
    schema_verified: bool = False
    application_smoke_verified: bool = False
    production_restore_performed: bool = False
    report_json: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BackupScheduleDefinition(_Strict):
    schedule_key: str
    schedule_type: str = "cron_spec"
    schedule_expression: str
    command_preview: str
    enabled: bool = False
    dry_run_validated: bool = False
    production_schedule_enabled: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class BackupRetentionPolicy(_Strict):
    policy_key: str
    keep_last: int = 7
    keep_daily: int = 7
    keep_weekly: int = 4
    keep_monthly: int = 3
    delete_enabled: bool = False
    dry_run_only: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class MigrationRollbackCatalogEntry(_Strict):
    migration_file: str
    migration_number: int | None = None
    reversibility: str = "unknown"
    down_script_available: bool = False
    rollback_notes: str | None = None
    risk_level: str = "low"
    verified: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class BackupReadinessEvaluation(_Strict):
    evaluation_key: str
    status: str = "passed_with_gaps"
    encryption_gap_closed: bool = False
    offhost_gap_closed: bool = False
    schedule_gap_closed: bool = False
    migration_down_gap_closed: bool = False
    remaining_gaps: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BackupDrVerificationResult(_Strict):
    """Aggregate verification result for the gap-closure run (no secrets)."""

    status: str = "failed"
    encryption_gap_closed: bool = False
    offhost_gap_closed: bool = False
    schedule_gap_closed: bool = False
    migration_down_gap_closed: bool = False
    remaining_gaps: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    raw_key_persisted: bool = False
    real_cloud_write_performed: bool = False
    production_backup_performed: bool = False
    production_restore_performed: bool = False
    production_schedule_enabled: bool = False
    production_executed: bool = False
    notes: list[str] = Field(default_factory=list)


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
    "KEY_SOURCES",
    "ENC_CONFIG_STATUSES",
    "BACKUP_ENVIRONMENTS",
    "BACKUP_RUN_STATUSES",
    "OFFHOST_TARGET_TYPES",
    "OFFHOST_TARGET_STATUSES",
    "OFFHOST_TRANSFER_STATUSES",
    "RESTORE_MODES",
    "RESTORE_STATUSES",
    "SCHEDULE_TYPES",
    "RETENTION_DRY_RUN_STATUSES",
    "REVERSIBILITY",
    "RISK_LEVELS",
    "READINESS_STATUSES",
]
