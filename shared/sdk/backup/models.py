"""Stage 36 -- shared dataclasses + constants."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

STORAGE_MODE_LOCAL = "local-filesystem"
STORAGE_MODE_S3 = "s3-compatible-placeholder"
STORAGE_MODE_DISABLED = "disabled"

RESTORE_DRILL_STATUS_PASSED = "passed"
RESTORE_DRILL_STATUS_FAILED = "failed"
RESTORE_DRILL_STATUS_NOT_RUN = "not_run"


@dataclass
class BackupArtifactRef:
    """Pointer to an on-disk backup artifact (no credential carried)."""

    backup_id: str
    artifact_path: str
    encrypted: bool
    encryption_mode: str
    checksum_sha256: str
    size_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "backup_id": self.backup_id,
            "artifact_path": self.artifact_path,
            "encrypted": self.encrypted,
            "encryption_mode": self.encryption_mode,
            "checksum_sha256": self.checksum_sha256,
            "size_bytes": self.size_bytes,
        }


@dataclass
class RestoreDrillReport:
    """Structured DR report.

    Persisted as ``source/dr-reports/dr_report_{timestamp}.json`` +
    ``dr_report_latest.json``. Never carries credentials.
    """

    drill_id: str
    started_at: str
    finished_at: str
    backup_id: str
    backup_artifact_path: str
    manifest_path: str
    restore_db: str
    status: str
    row_count_summary: dict[str, int] = field(default_factory=dict)
    audit_integrity_status: str = "not_run"
    audit_integrity_records_checked: int = 0
    audit_integrity_mismatches: int = 0
    backup_duration_seconds: float = 0.0
    encryption_duration_seconds: float = 0.0
    upload_duration_seconds: float = 0.0
    download_duration_seconds: float = 0.0
    restore_duration_seconds: float = 0.0
    integrity_verify_duration_seconds: float = 0.0
    total_drill_duration_seconds: float = 0.0
    estimated_rto_seconds: float = 0.0
    estimated_rpo_seconds: float | None = None
    rpo_status: str = "manual_only"
    cleanup_completed: bool = False
    off_host_uploaded: bool = False
    off_host_uri: str | None = None
    encrypted: bool = False
    encryption_mode: str = "none"
    production_executed: bool = False
    failure_reason: str | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "drill_id": self.drill_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "backup_id": self.backup_id,
            "backup_artifact_path": self.backup_artifact_path,
            "manifest_path": self.manifest_path,
            "restore_db": self.restore_db,
            "status": self.status,
            "row_count_summary": dict(self.row_count_summary),
            "audit_integrity_status": self.audit_integrity_status,
            "audit_integrity_records_checked": int(self.audit_integrity_records_checked),
            "audit_integrity_mismatches": int(self.audit_integrity_mismatches),
            "backup_duration_seconds": float(self.backup_duration_seconds),
            "encryption_duration_seconds": float(self.encryption_duration_seconds),
            "upload_duration_seconds": float(self.upload_duration_seconds),
            "download_duration_seconds": float(self.download_duration_seconds),
            "restore_duration_seconds": float(self.restore_duration_seconds),
            "integrity_verify_duration_seconds": float(self.integrity_verify_duration_seconds),
            "total_drill_duration_seconds": float(self.total_drill_duration_seconds),
            "estimated_rto_seconds": float(self.estimated_rto_seconds),
            "estimated_rpo_seconds": (
                None if self.estimated_rpo_seconds is None else float(self.estimated_rpo_seconds)
            ),
            "rpo_status": self.rpo_status,
            "cleanup_completed": bool(self.cleanup_completed),
            "off_host_uploaded": bool(self.off_host_uploaded),
            "off_host_uri": self.off_host_uri,
            "encrypted": bool(self.encrypted),
            "encryption_mode": self.encryption_mode,
            "production_executed": bool(self.production_executed),
            "failure_reason": self.failure_reason,
            "notes": list(self.notes),
        }
