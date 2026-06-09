"""Stage 36 -- pluggable off-host storage interface.

Modes (env: ``BACKUP_STORAGE_MODE``):

  * ``local-filesystem`` -- copy artifact into ``BACKUP_STORAGE_BUCKET``
    + ``BACKUP_STORAGE_PREFIX``. Always real.
  * ``s3-compatible-placeholder`` -- placeholder for an S3-compatible
    target. Real upload is NOT implemented in Stage 36; if credentials
    are present we record the *intent* and emit a ``skipped`` decision
    that explicitly says ``s3_upload_not_implemented`` so operators
    cannot confuse "wired" with "uploaded".
  * ``disabled`` -- off-host upload is intentionally disabled.

If credentials are missing for the configured mode, the upload SKIPS
with ``credential_missing`` and the verify scripts pass with a
PASS_WITH_GAPS marker. The interface NEVER returns a credential value.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import STORAGE_MODE_DISABLED, STORAGE_MODE_LOCAL, STORAGE_MODE_S3

BACKUP_STORAGE_MODE_ENV = "BACKUP_STORAGE_MODE"
BACKUP_STORAGE_BUCKET_ENV = "BACKUP_STORAGE_BUCKET"
BACKUP_STORAGE_PREFIX_ENV = "BACKUP_STORAGE_PREFIX"
BACKUP_STORAGE_ENDPOINT_ENV = "BACKUP_STORAGE_ENDPOINT"
BACKUP_STORAGE_ACCESS_KEY_ID_ENV = "BACKUP_STORAGE_ACCESS_KEY_ID"
BACKUP_STORAGE_SECRET_ACCESS_KEY_ENV = "BACKUP_STORAGE_SECRET_ACCESS_KEY"


@dataclass
class StorageDecision:
    """Outcome of one upload/download attempt."""

    mode: str
    uploaded: bool
    skipped: bool
    reason: str
    uri: str | None
    bytes_transferred: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "uploaded": bool(self.uploaded),
            "skipped": bool(self.skipped),
            "reason": self.reason,
            "uri": self.uri,
            "bytes_transferred": int(self.bytes_transferred),
        }


def storage_status(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Operations-API-safe view of the storage config (no credential value)."""

    source: Mapping[str, str] = env if env is not None else os.environ
    mode = (source.get(BACKUP_STORAGE_MODE_ENV) or STORAGE_MODE_LOCAL).strip()
    if mode not in (STORAGE_MODE_LOCAL, STORAGE_MODE_S3, STORAGE_MODE_DISABLED):
        mode = STORAGE_MODE_DISABLED
    has_bucket = bool(source.get(BACKUP_STORAGE_BUCKET_ENV))
    has_access_key = bool(source.get(BACKUP_STORAGE_ACCESS_KEY_ID_ENV))
    has_secret_key = bool(source.get(BACKUP_STORAGE_SECRET_ACCESS_KEY_ENV))
    has_endpoint = bool(source.get(BACKUP_STORAGE_ENDPOINT_ENV))
    return {
        "mode": mode,
        "bucket_configured": has_bucket,
        "prefix_configured": bool(source.get(BACKUP_STORAGE_PREFIX_ENV)),
        "endpoint_configured": has_endpoint,
        "access_key_configured": has_access_key,
        "secret_key_configured": has_secret_key,
        "credential_complete": (
            mode == STORAGE_MODE_LOCAL
            and has_bucket
            or (mode == STORAGE_MODE_S3 and has_bucket and has_access_key and has_secret_key)
        ),
        "production_ready": (
            mode == STORAGE_MODE_S3 and has_bucket and has_access_key and has_secret_key
        ),
    }


class BackupStorage:
    """Off-host storage facade.

    Local-filesystem mode is the only real upload Stage 36 ships; the
    S3 mode is a wired interface that intentionally emits a ``skipped``
    decision with reason=``s3_upload_not_implemented`` so an operator
    knows the artifact still lives on-host.
    """

    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        self._env: dict[str, str] = dict(env if env is not None else os.environ)

    @property
    def mode(self) -> str:
        mode = (self._env.get(BACKUP_STORAGE_MODE_ENV) or STORAGE_MODE_LOCAL).strip()
        if mode not in (STORAGE_MODE_LOCAL, STORAGE_MODE_S3, STORAGE_MODE_DISABLED):
            return STORAGE_MODE_DISABLED
        return mode

    def upload(self, source_path: str | Path, backup_id: str) -> StorageDecision:
        """Upload a single artifact (or skip if not configured)."""

        src = Path(source_path)
        if not src.is_file():
            return StorageDecision(
                mode=self.mode,
                uploaded=False,
                skipped=True,
                reason="source_artifact_missing",
                uri=None,
                bytes_transferred=0,
            )

        if self.mode == STORAGE_MODE_DISABLED:
            return StorageDecision(
                mode=STORAGE_MODE_DISABLED,
                uploaded=False,
                skipped=True,
                reason="storage_mode_disabled",
                uri=None,
            )

        if self.mode == STORAGE_MODE_LOCAL:
            return self._upload_local(src, backup_id)

        # s3-compatible-placeholder
        bucket = self._env.get(BACKUP_STORAGE_BUCKET_ENV)
        access_key = self._env.get(BACKUP_STORAGE_ACCESS_KEY_ID_ENV)
        secret_key = self._env.get(BACKUP_STORAGE_SECRET_ACCESS_KEY_ENV)
        if not (bucket and access_key and secret_key):
            return StorageDecision(
                mode=STORAGE_MODE_S3,
                uploaded=False,
                skipped=True,
                reason="credential_missing",
                uri=None,
            )
        # Stage 36 intentionally does NOT ship a real S3 client. The
        # interface is wired so a future stage can drop in boto3 / minio
        # without changing the operations API surface.
        return StorageDecision(
            mode=STORAGE_MODE_S3,
            uploaded=False,
            skipped=True,
            reason="s3_upload_not_implemented",
            uri=None,
        )

    def download(self, uri: str, target_path: str | Path) -> StorageDecision:
        target = Path(target_path)
        if self.mode == STORAGE_MODE_DISABLED:
            return StorageDecision(
                mode=STORAGE_MODE_DISABLED,
                uploaded=False,
                skipped=True,
                reason="storage_mode_disabled",
                uri=uri,
            )

        if self.mode == STORAGE_MODE_LOCAL:
            return self._download_local(uri, target)

        return StorageDecision(
            mode=STORAGE_MODE_S3,
            uploaded=False,
            skipped=True,
            reason="s3_download_not_implemented",
            uri=uri,
        )

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------

    def _upload_local(self, src: Path, backup_id: str) -> StorageDecision:
        bucket = self._env.get(BACKUP_STORAGE_BUCKET_ENV)
        if not bucket:
            return StorageDecision(
                mode=STORAGE_MODE_LOCAL,
                uploaded=False,
                skipped=True,
                reason="credential_missing",
                uri=None,
            )
        prefix = self._env.get(BACKUP_STORAGE_PREFIX_ENV) or backup_id
        bucket_path = Path(bucket).expanduser()
        bucket_path.mkdir(parents=True, exist_ok=True)
        target_dir = bucket_path / prefix
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / src.name
        shutil.copy2(src, target_path)
        size = target_path.stat().st_size
        return StorageDecision(
            mode=STORAGE_MODE_LOCAL,
            uploaded=True,
            skipped=False,
            reason="ok",
            uri=str(target_path),
            bytes_transferred=size,
        )

    def _download_local(self, uri: str, target: Path) -> StorageDecision:
        src = Path(uri)
        if not src.is_file():
            return StorageDecision(
                mode=STORAGE_MODE_LOCAL,
                uploaded=False,
                skipped=True,
                reason="off_host_artifact_missing",
                uri=uri,
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        size = target.stat().st_size
        return StorageDecision(
            mode=STORAGE_MODE_LOCAL,
            uploaded=True,
            skipped=False,
            reason="ok",
            uri=str(target),
            bytes_transferred=size,
        )
