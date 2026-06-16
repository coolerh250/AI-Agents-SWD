"""Stage 51 -- isolated restore drill (test DB only).

The shell verify (``scripts/verify_backup_restore_drill.sh``) decrypts the
backup and restores it into a throwaway isolated database. This module provides
the non-production guard, the isolated DB-name helper (reusing the Stage 36
prefix), and the secret-free ``RestoreDrillRun`` report builder. Production
restore is never performed.
"""

from __future__ import annotations

from shared.sdk.backup.restore import DEFAULT_RESTORE_DB_PREFIX, isolated_restore_db_name
from shared.sdk.backup_dr.backup_runner import ProductionBackupBlocked
from shared.sdk.backup_dr.models import RestoreDrillRun


def assert_isolated_target(target_database: str) -> None:
    """Ensure the restore target is an isolated drill DB, never production."""
    name = (target_database or "").strip().lower()
    if not name:
        raise ProductionBackupBlocked("restore drill target database is empty")
    if name in ("aiagents", "postgres", "production") or name.endswith("_production"):
        raise ProductionBackupBlocked(
            f"restore drill refuses to target a non-isolated database: {target_database}"
        )


def build_restore_drill_run(
    *,
    restore_key: str,
    target_database: str,
    backup_run_id: str | None = None,
    restore_mode: str = "isolated_test_db",
    status: str = "verified",
    rto_seconds: float | None = None,
    row_count_verified: bool = False,
    schema_verified: bool = False,
    application_smoke_verified: bool = False,
    report: dict | None = None,
) -> RestoreDrillRun:
    """Build a secret-free restore drill record. production_restore_performed
    is always false."""
    if restore_mode == "isolated_test_db":
        assert_isolated_target(target_database)
    return RestoreDrillRun(
        backup_run_id=backup_run_id,
        restore_key=restore_key,
        target_database=target_database,
        restore_mode=restore_mode,
        status=status,
        rto_seconds=rto_seconds,
        row_count_verified=row_count_verified,
        schema_verified=schema_verified,
        application_smoke_verified=application_smoke_verified,
        production_restore_performed=False,
        report_json=dict(report or {}),
        metadata={"controlled_only": True},
    )


def restore_drill_ok(drill: RestoreDrillRun) -> bool:
    return (
        drill.status in ("restored", "verified")
        and drill.schema_verified
        and drill.row_count_verified
        and not drill.production_restore_performed
    )


__all__ = [
    "DEFAULT_RESTORE_DB_PREFIX",
    "isolated_restore_db_name",
    "assert_isolated_target",
    "build_restore_drill_run",
    "restore_drill_ok",
]
