"""Stage 51 -- backup manifest builder (no raw key / no DB password).

Reuses ``shared.sdk.backup.checksum`` for artifact integrity. The manifest
carries only the encryption *key_id* label (never the key) and never any DB
password / credential value.
"""

from __future__ import annotations

from typing import Any

from shared.sdk.backup_dr.models import BackupEncryptionConfig, BackupManifest, BackupRun


def build_manifest(
    *,
    backup_run: BackupRun,
    encryption: BackupEncryptionConfig | None,
    schema_migration_count: int | None = None,
    table_count: int | None = None,
    row_count_summary: dict[str, int] | None = None,
    backup_run_id: str | None = None,
) -> BackupManifest:
    """Build a deterministic, secret-free backup manifest."""
    enc_key_id = encryption.key_id if encryption else None
    enc_algorithm = encryption.algorithm if encryption else None
    manifest_json: dict[str, Any] = {
        "backup_key": backup_run.backup_key,
        "source_database": backup_run.source_database,
        "environment": backup_run.environment,
        "encrypted": backup_run.encrypted,
        "schema_migration_count": schema_migration_count,
        "table_count": table_count,
        "row_count_summary": dict(row_count_summary or {}),
        "artifact_checksum_sha256": backup_run.checksum_sha256,
        "encrypted_artifact_checksum_sha256": backup_run.encrypted_checksum_sha256,
        "encryption_algorithm": enc_algorithm,
        "encryption_key_id": enc_key_id,
        "production_executed": False,
    }
    return BackupManifest(
        backup_run_id=backup_run_id,
        manifest_version="1",
        source_database=backup_run.source_database,
        schema_migration_count=schema_migration_count,
        table_count=table_count,
        row_count_summary=dict(row_count_summary or {}),
        artifact_checksum_sha256=backup_run.checksum_sha256,
        encrypted_artifact_checksum_sha256=backup_run.encrypted_checksum_sha256,
        encryption_key_id=enc_key_id,
        encryption_algorithm=enc_algorithm,
        manifest_json=manifest_json,
    )


_FORBIDDEN_FRAGMENTS = (
    "password",
    "secret",
    "token",
    "private_key",
    "-----begin",
)


def manifest_contains_secret(manifest: BackupManifest) -> bool:
    """Defensive check: the manifest must never carry a secret-like value."""
    import json

    blob = json.dumps(manifest.model_dump(), default=str).lower()
    return any(frag in blob for frag in _FORBIDDEN_FRAGMENTS)


__all__ = ["build_manifest", "manifest_contains_secret"]
