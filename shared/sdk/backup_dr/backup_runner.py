"""Stage 51 -- backup run orchestration (test / dev only).

The heavy lifting (pg_dump + openssl encrypt) runs in shell
(``scripts/run_encrypted_backup.sh``) so crypto + dump are auditable and the
key only lives in openssl's address space. This module provides the
non-production guard + the secret-free ``BackupRun`` record builder, and a thin
``run_pg_dump`` helper that refuses to run against a production database.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from shared.sdk.backup.checksum import compute_sha256
from shared.sdk.backup_dr.models import BackupRun

PRODUCTION_ENVIRONMENT = "production"


class ProductionBackupBlocked(RuntimeError):
    """Raised when a backup is attempted against a production environment."""


def assert_non_production(environment: str) -> None:
    if (environment or "").strip().lower() == PRODUCTION_ENVIRONMENT:
        raise ProductionBackupBlocked(
            "Stage 51 backup runner refuses to operate on a production environment"
        )


def build_backup_run(
    *,
    backup_key: str,
    source_database: str,
    environment: str = "test",
    encrypted: bool = False,
    encryption_config_id: str | None = None,
    artifact_path: str | None = None,
    manifest_path: str | None = None,
    checksum_sha256: str | None = None,
    encrypted_checksum_sha256: str | None = None,
    size_bytes: int | None = None,
    status: str = "completed",
) -> BackupRun:
    """Build a secret-free ``BackupRun`` record. Never sets production_executed."""
    assert_non_production(environment)
    return BackupRun(
        backup_key=backup_key,
        environment=environment,
        source_database=source_database,
        status=status,
        encrypted=encrypted,
        encryption_config_id=encryption_config_id,
        artifact_path=artifact_path,
        manifest_path=manifest_path,
        checksum_sha256=checksum_sha256,
        encrypted_checksum_sha256=encrypted_checksum_sha256,
        size_bytes=size_bytes,
        production_executed=False,
        metadata={"controlled_only": True},
    )


def run_pg_dump(
    *,
    database_url: str,
    output_path: str | Path,
    environment: str = "test",
) -> tuple[str, int]:
    """Run ``pg_dump`` to ``output_path`` (test/dev only). Returns (sha256, size).

    Refuses to run against a production environment. The shell verify scripts
    are the primary driver; this helper exists for parity + tests that mock
    subprocess.
    """
    assert_non_production(environment)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as fh:
        subprocess.run(  # noqa: S603 -- fixed argv, no shell
            ["pg_dump", "--no-owner", "--no-privileges", database_url],
            stdout=fh,
            check=True,
        )
    return compute_sha256(out), out.stat().st_size


__all__ = [
    "PRODUCTION_ENVIRONMENT",
    "ProductionBackupBlocked",
    "assert_non_production",
    "build_backup_run",
    "run_pg_dump",
]
