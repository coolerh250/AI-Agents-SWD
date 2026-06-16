"""Stage 51 -- mock off-host target abstraction.

Builds a mock off-host target (a separate local directory standing in for a
remote host) and recognises S3 / GCS / Azure target configs but keeps real
cloud write DISABLED. No real cloud client ships in this stage.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from shared.sdk.backup_dr.models import BackupOffhostTarget

DEFAULT_OFFHOST_DIR_ENV = "BACKUP_DR_OFFHOST_DIR"
DEFAULT_OFFHOST_DIR = "/tmp/aiagents-offhost-backups"


def resolve_offhost_dir(env: Mapping[str, str] | None = None) -> Path:
    source = env if env is not None else os.environ
    raw = (source.get(DEFAULT_OFFHOST_DIR_ENV) or DEFAULT_OFFHOST_DIR).strip()
    return Path(raw).expanduser()


def build_mock_offhost_target(
    *,
    target_key: str = "mock-offhost-test",
    env: Mapping[str, str] | None = None,
    create: bool = True,
) -> BackupOffhostTarget:
    """Build (and optionally create) a mock off-host target directory.

    Real cloud write stays disabled. If env declares a cloud target type its
    config is recorded as ``*_disabled`` with ``real_cloud_write_enabled=false``.
    """
    source = env if env is not None else os.environ
    cloud = (source.get("BACKUP_DR_CLOUD_TARGET_TYPE") or "").strip().lower()
    if cloud in ("s3", "gcs", "azure"):
        target_type = f"{cloud}_disabled"
        return BackupOffhostTarget(
            target_key=target_key,
            target_type=target_type,
            target_uri=(source.get("BACKUP_DR_CLOUD_TARGET_URI") or f"{cloud}://disabled"),
            status="disabled",
            real_cloud_write_enabled=False,
            test_only=True,
            metadata={"cloud_target_recognized": cloud, "real_cloud_write_enabled": False},
        )

    offhost_dir = resolve_offhost_dir(source)
    if create:
        offhost_dir.mkdir(parents=True, exist_ok=True)
    return BackupOffhostTarget(
        target_key=target_key,
        target_type="mock_local_remote",
        target_uri=str(offhost_dir),
        status="configured",
        real_cloud_write_enabled=False,
        test_only=True,
        metadata={"mock_off_host": True},
    )


def safe_status(target: BackupOffhostTarget) -> dict[str, object]:
    return {
        "target_key": target.target_key,
        "target_type": target.target_type,
        "target_uri": target.target_uri,
        "status": target.status,
        "real_cloud_write_enabled": target.real_cloud_write_enabled,
        "test_only": target.test_only,
    }


__all__ = [
    "DEFAULT_OFFHOST_DIR_ENV",
    "DEFAULT_OFFHOST_DIR",
    "resolve_offhost_dir",
    "build_mock_offhost_target",
    "safe_status",
]
