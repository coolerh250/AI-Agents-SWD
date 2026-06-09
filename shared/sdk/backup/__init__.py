"""Stage 36 -- Backup / Restore / DR SDK.

This package owns the production-readiness pieces for backup + restore:

  * ``BackupManifest`` -- deterministic JSON description of a single
    backup artifact (paths, sha256, encryption flag, off-host upload
    state, schema version, row counts...).
  * ``compute_sha256`` / ``verify_sha256`` -- artifact integrity.
  * ``encrypt_artifact`` / ``decrypt_artifact`` -- AES-256-CBC + HMAC
    wrapper around openssl. Never logs the key. Key material comes
    from ``BACKUP_ENCRYPTION_KEY`` (env) or a test-only generated
    keyfile under /tmp.
  * ``BackupStorage`` -- pluggable off-host interface
    (local-filesystem / s3-compatible-placeholder / disabled). Real
    S3 upload is NOT performed in Stage 36 -- the interface returns a
    ``skipped`` decision when credentials are absent, which is the
    spec-mandated behaviour.
  * ``RestoreDrillReport`` -- structured DR report (RTO, RPO, row
    count verification, audit integrity verification, cleanup
    state).

Every public function in this package is safe to log: nothing returns
or carries an encryption key value, a storage credential value, or a
database password.
"""

from __future__ import annotations

from .checksum import compute_sha256, verify_sha256
from .encryption import (
    BACKUP_ENCRYPTION_KEY_ENV,
    EncryptionConfig,
    EncryptionResult,
    encryption_status,
    resolve_encryption_key_source,
)
from .manifest import (
    MANIFEST_SCHEMA_VERSION,
    BackupManifest,
    load_manifest,
    write_manifest,
)
from .models import (
    RESTORE_DRILL_STATUS_FAILED,
    RESTORE_DRILL_STATUS_NOT_RUN,
    RESTORE_DRILL_STATUS_PASSED,
    STORAGE_MODE_DISABLED,
    STORAGE_MODE_LOCAL,
    STORAGE_MODE_S3,
    BackupArtifactRef,
    RestoreDrillReport,
)
from .restore import (
    DEFAULT_RESTORE_DB_PREFIX,
    isolated_restore_db_name,
)
from .storage import (
    BackupStorage,
    StorageDecision,
    storage_status,
)

__all__ = [
    "BACKUP_ENCRYPTION_KEY_ENV",
    "BackupArtifactRef",
    "BackupManifest",
    "BackupStorage",
    "DEFAULT_RESTORE_DB_PREFIX",
    "EncryptionConfig",
    "EncryptionResult",
    "MANIFEST_SCHEMA_VERSION",
    "RESTORE_DRILL_STATUS_FAILED",
    "RESTORE_DRILL_STATUS_NOT_RUN",
    "RESTORE_DRILL_STATUS_PASSED",
    "RestoreDrillReport",
    "STORAGE_MODE_DISABLED",
    "STORAGE_MODE_LOCAL",
    "STORAGE_MODE_S3",
    "StorageDecision",
    "compute_sha256",
    "encryption_status",
    "isolated_restore_db_name",
    "load_manifest",
    "resolve_encryption_key_source",
    "storage_status",
    "verify_sha256",
    "write_manifest",
]
