"""Stage 51 -- backup encryption config resolution (metadata only).

Extends the Stage 36 ``shared.sdk.backup.encryption`` key-source resolution to
the Step 49 readiness model. This module NEVER reads or returns a raw key
value:

  * test-only key file (default): a chmod-600 file under a runtime / gitignored
    path. ``key_id`` is a short sha256 prefix of the *file contents* -- enough
    to detect "did the key change?" without exposing the key.
  * mock_vault / env_reference: metadata only; the value lives outside the
    process.
  * disabled / missing: clearly flagged ``encryption_no_key`` so the gap is
    visible.

The actual openssl encrypt happens in shell (scripts/run_encrypted_backup.sh)
so crypto is auditable and the key only ever lives in openssl's address space.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping
from pathlib import Path

from shared.sdk.backup_dr.models import BackupEncryptionConfig

# Safe runtime paths (gitignored / outside repo). The first existing one wins.
DEFAULT_KEY_FILE_ENV = "BACKUP_DR_TEST_KEY_FILE"
DEFAULT_KEY_FILE_PATHS = (
    ".runtime/backup-test-key",
    "/tmp/aiagents-backup-test-key",
)
DEFAULT_ALGORITHM = "openssl-aes-256-cbc"

GAP_ENCRYPTION_NO_KEY = "encryption_no_key"


def _key_id_for_file(path: Path) -> str:
    """Short opaque label for a key file -- sha256(contents)[:12], never the key."""
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest()[:12]


def resolve_key_file_path(env: Mapping[str, str] | None = None) -> Path | None:
    """Return the configured/first-existing test key file path, or None."""
    source = env if env is not None else os.environ
    explicit = (source.get(DEFAULT_KEY_FILE_ENV) or "").strip()
    candidates = [explicit] if explicit else list(DEFAULT_KEY_FILE_PATHS)
    for cand in candidates:
        if not cand:
            continue
        p = Path(cand).expanduser()
        if p.is_file():
            return p
    return None


def resolve_encryption_config(
    *,
    config_key: str = "backup-dr-test",
    env: Mapping[str, str] | None = None,
) -> BackupEncryptionConfig:
    """Resolve the encryption config metadata for the readiness baseline.

    Precedence: a present test-only key file (real, ephemeral) closes the
    encryption gap at the baseline level; an explicit mock_vault / env_reference
    is recorded as metadata; otherwise the config is ``missing`` and the
    ``encryption_no_key`` gap remains open.
    """
    source = env if env is not None else os.environ

    key_file = resolve_key_file_path(source)
    if key_file is not None:
        return BackupEncryptionConfig(
            config_key=config_key,
            key_source="key_file",
            key_ref=str(key_file),
            key_id=_key_id_for_file(key_file),
            algorithm=DEFAULT_ALGORITHM,
            status="configured",
            production_usable=False,
            test_only=True,
            metadata={"runtime_path": True},
        )

    vault_ref = (source.get("BACKUP_DR_MOCK_VAULT_REF") or "").strip()
    if vault_ref:
        return BackupEncryptionConfig(
            config_key=config_key,
            key_source="mock_vault",
            key_ref=vault_ref,
            key_id=hashlib.sha256(vault_ref.encode()).hexdigest()[:12],
            algorithm=DEFAULT_ALGORITHM,
            status="configured",
            production_usable=False,
            test_only=True,
            metadata={"mock_vault": True},
        )

    env_ref = (source.get("BACKUP_DR_ENCRYPTION_ENV_REF") or "").strip()
    if env_ref and source.get(env_ref):
        return BackupEncryptionConfig(
            config_key=config_key,
            key_source="env_reference",
            key_ref=env_ref,
            key_id=hashlib.sha256((source.get(env_ref) or "").encode()).hexdigest()[:12],
            algorithm=DEFAULT_ALGORITHM,
            status="configured",
            production_usable=bool(source.get("BACKUP_DR_ENCRYPTION_PRODUCTION_USABLE")),
            test_only=not bool(source.get("BACKUP_DR_ENCRYPTION_PRODUCTION_USABLE")),
            metadata={"env_reference": True},
        )

    return BackupEncryptionConfig(
        config_key=config_key,
        key_source="disabled",
        key_ref=None,
        key_id=None,
        algorithm=DEFAULT_ALGORITHM,
        status="missing",
        production_usable=False,
        test_only=True,
        metadata={"gap": GAP_ENCRYPTION_NO_KEY},
    )


def encryption_gap_closed(config: BackupEncryptionConfig) -> bool:
    """The encryption gap is closed at the baseline level when a real key is
    configured (key_file / mock_vault / env_reference) with a derived key_id."""
    return config.status == "configured" and bool(config.key_id)


def safe_status(config: BackupEncryptionConfig) -> dict[str, object]:
    """Operations-API-safe view (no raw key, no secret)."""
    return {
        "config_key": config.config_key,
        "key_source": config.key_source,
        "key_id": config.key_id,
        "algorithm": config.algorithm,
        "status": config.status,
        "production_usable": config.production_usable,
        "test_only": config.test_only,
        "raw_key_persisted": False,
        "gap_closed": encryption_gap_closed(config),
    }


__all__ = [
    "DEFAULT_KEY_FILE_ENV",
    "DEFAULT_KEY_FILE_PATHS",
    "DEFAULT_ALGORITHM",
    "GAP_ENCRYPTION_NO_KEY",
    "resolve_key_file_path",
    "resolve_encryption_config",
    "encryption_gap_closed",
    "safe_status",
]
