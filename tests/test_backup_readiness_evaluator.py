"""Stage 51 -- readiness evaluator closes the four gaps with limitations."""

from __future__ import annotations

from shared.sdk.backup_dr.encryption_config import resolve_encryption_config
from shared.sdk.backup_dr.migration_catalog import build_migration_catalog
from shared.sdk.backup_dr.models import (
    BackupScheduleDefinition,
    OffhostTransferRun,
    RestoreDrillRun,
)
from shared.sdk.backup_dr.offhost_target import build_mock_offhost_target
from shared.sdk.backup_dr.offhost_transfer import transfer_to_offhost
from shared.sdk.backup_dr.readiness_evaluator import (
    NON_PRODUCTION_LIMITATIONS,
    evaluate_readiness,
)
from shared.sdk.backup_dr.schedule_builder import build_cron_spec


def _all_closed_inputs(tmp_path, monkeypatch):
    keyf = tmp_path / "k"
    keyf.write_text("key", encoding="utf-8")
    monkeypatch.setenv("BACKUP_DR_TEST_KEY_FILE", str(keyf))
    monkeypatch.setenv("BACKUP_DR_OFFHOST_DIR", str(tmp_path / "offhost"))
    art = tmp_path / "b.enc"
    art.write_bytes(b"ENC")
    enc = resolve_encryption_config()
    target = build_mock_offhost_target()
    transfer = transfer_to_offhost(source_path=str(art), target=target)
    schedule = build_cron_spec()
    entries = build_migration_catalog("migrations")
    restore = RestoreDrillRun(
        restore_key="r",
        target_database="aiagents_restore_drill_x",
        status="verified",
        schema_verified=True,
        row_count_verified=True,
        rto_seconds=3.0,
    )
    return enc, transfer, schedule, entries, restore


def test_all_gaps_closed_non_production_limitations(tmp_path, monkeypatch) -> None:
    enc, transfer, schedule, entries, restore = _all_closed_inputs(tmp_path, monkeypatch)
    ev = evaluate_readiness(
        encryption=enc,
        transfer=transfer,
        schedule=schedule,
        migration_entries=entries,
        restore=restore,
    )
    assert ev.encryption_gap_closed is True
    assert ev.offhost_gap_closed is True
    assert ev.schedule_gap_closed is True
    assert ev.migration_down_gap_closed is True
    assert ev.remaining_gaps == []
    assert ev.status == "passed_with_non_production_limitations"
    assert set(NON_PRODUCTION_LIMITATIONS).issubset(set(ev.limitations))


def test_open_gap_keeps_passed_with_gaps(tmp_path, monkeypatch) -> None:
    enc, transfer, schedule, entries, restore = _all_closed_inputs(tmp_path, monkeypatch)
    bad_transfer = OffhostTransferRun(status="failed", readback_verified=False)
    ev = evaluate_readiness(
        encryption=enc,
        transfer=bad_transfer,
        schedule=schedule,
        migration_entries=entries,
        restore=restore,
    )
    assert "storage_not_off_host" in ev.remaining_gaps
    assert ev.status == "passed_with_gaps"


def test_disabled_schedule_required(tmp_path, monkeypatch) -> None:
    enc, transfer, _schedule, entries, restore = _all_closed_inputs(tmp_path, monkeypatch)
    enabled = BackupScheduleDefinition(
        schedule_key="s",
        schedule_expression="0 2 * * *",
        command_preview="x",
        dry_run_validated=True,
        production_schedule_enabled=True,
    )
    ev = evaluate_readiness(
        encryption=enc,
        transfer=transfer,
        schedule=enabled,
        migration_entries=entries,
        restore=restore,
    )
    assert "schedule_dry_run_only" in ev.remaining_gaps
