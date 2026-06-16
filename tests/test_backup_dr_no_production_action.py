"""Stage 51 -- no production backup / restore / cloud write / schedule action."""

from __future__ import annotations

import pytest

from shared.sdk.backup_dr.backup_runner import (
    ProductionBackupBlocked,
    assert_non_production,
    build_backup_run,
)
from shared.sdk.backup_dr.report_builder import build_gap_closure_report
from shared.sdk.backup_dr.encryption_config import resolve_encryption_config
from shared.sdk.backup_dr.manifest_builder import build_manifest
from shared.sdk.backup_dr.migration_catalog import build_migration_catalog
from shared.sdk.backup_dr.offhost_target import build_mock_offhost_target
from shared.sdk.backup_dr.offhost_transfer import transfer_to_offhost
from shared.sdk.backup_dr.readiness_evaluator import evaluate_readiness
from shared.sdk.backup_dr.retention_policy import build_retention_policy, compute_retention_dry_run
from shared.sdk.backup_dr.schedule_builder import build_cron_spec


def test_build_backup_run_blocks_production() -> None:
    with pytest.raises(ProductionBackupBlocked):
        build_backup_run(backup_key="b", source_database="db", environment="production")


def test_assert_non_production() -> None:
    assert_non_production("test")  # no raise
    with pytest.raises(ProductionBackupBlocked):
        assert_non_production("production")


def test_run_pg_dump_blocks_production() -> None:
    from shared.sdk.backup_dr.backup_runner import run_pg_dump

    with pytest.raises(ProductionBackupBlocked):
        run_pg_dump(database_url="x", output_path="/tmp/x.dump", environment="production")


def test_report_asserts_no_production(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BACKUP_DR_OFFHOST_DIR", str(tmp_path / "offhost"))
    art = tmp_path / "b.enc"
    art.write_bytes(b"ENC")
    enc = resolve_encryption_config()
    run = build_backup_run(backup_key="b", source_database="aiagents", encrypted=True)
    manifest = build_manifest(backup_run=run, encryption=enc)
    target = build_mock_offhost_target()
    transfer = transfer_to_offhost(source_path=str(art), target=target)
    schedule = build_cron_spec()
    entries = build_migration_catalog("migrations")
    retention = compute_retention_dry_run(build_retention_policy(), [])
    readiness = evaluate_readiness(
        encryption=enc,
        transfer=transfer,
        schedule=schedule,
        migration_entries=entries,
        restore=None,
    )
    report = build_gap_closure_report(
        encryption=enc,
        backup_run=run,
        manifest=manifest,
        offhost_target=target,
        transfer=transfer,
        restore=None,
        schedule=schedule,
        retention_dry_run=retention,
        migration_entries=entries,
        readiness=readiness,
    )
    ev = report["safety_evidence"]
    assert ev["production_backup_performed"] is False
    assert ev["production_restore_performed"] is False
    assert ev["real_cloud_write_performed"] is False
    assert ev["production_schedule_enabled"] is False
    assert ev["production_executed"] is False
