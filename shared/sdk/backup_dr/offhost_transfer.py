"""Stage 51 -- off-host transfer + readback verification.

Copies an (encrypted) backup artifact to the mock off-host target and verifies
the readback checksum. Real cloud write is never performed. Reuses
``shared.sdk.backup.checksum`` for integrity.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from shared.sdk.backup.checksum import compute_sha256
from shared.sdk.backup_dr.models import BackupOffhostTarget, OffhostTransferRun


def transfer_to_offhost(
    *,
    source_path: str | Path,
    target: BackupOffhostTarget,
    backup_run_id: str | None = None,
    target_id: str | None = None,
) -> OffhostTransferRun:
    """Copy the artifact to the mock off-host target and verify readback.

    Never writes a real cloud bucket. A disabled cloud target results in a
    ``skipped`` transfer (still no gap regression -- the mock path is the
    baseline closure).
    """
    src = Path(source_path)
    if target.target_type != "mock_local_remote" or target.status != "configured":
        return OffhostTransferRun(
            backup_run_id=backup_run_id,
            target_id=target_id,
            status="skipped",
            source_path=str(src),
            readback_verified=False,
            real_cloud_write_performed=False,
            metadata={"reason": "cloud_target_disabled", "target_type": target.target_type},
        )

    if not src.is_file():
        return OffhostTransferRun(
            backup_run_id=backup_run_id,
            target_id=target_id,
            status="failed",
            source_path=str(src),
            readback_verified=False,
            real_cloud_write_performed=False,
            metadata={"reason": "source_artifact_missing"},
        )

    source_checksum = compute_sha256(src)
    target_dir = Path(target.target_uri).expanduser()
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / src.name
    shutil.copy2(src, target_path)
    target_checksum = compute_sha256(target_path)
    verified = source_checksum == target_checksum

    return OffhostTransferRun(
        backup_run_id=backup_run_id,
        target_id=target_id,
        status="verified" if verified else "failed",
        source_path=str(src),
        target_path=str(target_path),
        source_checksum_sha256=source_checksum,
        target_checksum_sha256=target_checksum,
        readback_verified=verified,
        real_cloud_write_performed=False,
        metadata={"mock_off_host": True},
    )


def offhost_gap_closed(transfer: OffhostTransferRun) -> bool:
    """Closed when an artifact is copied off-host and readback verified, with
    no real cloud write performed."""
    return (
        transfer.status == "verified"
        and transfer.readback_verified
        and not transfer.real_cloud_write_performed
    )


__all__ = ["transfer_to_offhost", "offhost_gap_closed"]
