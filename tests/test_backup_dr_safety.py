"""Stage 51 -- backup / DR safety flags + controlled-only invariants."""

from __future__ import annotations

from shared.sdk.backup_dr.models import (
    BackupEncryptionConfig,
    BackupOffhostTarget,
    BackupReadinessEvaluation,
    BackupRun,
    BackupScheduleDefinition,
    OffhostTransferRun,
    RestoreDrillRun,
)
from shared.sdk.backup_dr.safety import (
    assert_controlled_only,
    backup_dr_safety_flags,
)


def test_safety_flags_controlled() -> None:
    flags = backup_dr_safety_flags(
        encryption=BackupEncryptionConfig(config_key="c", status="configured", key_id="x"),
        backup_run=BackupRun(backup_key="b", source_database="aiagents", encrypted=True),
        offhost_target=BackupOffhostTarget(target_key="t", target_uri="/tmp/x"),
        transfer=OffhostTransferRun(status="verified", readback_verified=True),
        restore=RestoreDrillRun(
            restore_key="r",
            target_database="aiagents_restore_drill_x",
            status="verified",
            rto_seconds=2.0,
        ),
        schedule=BackupScheduleDefinition(
            schedule_key="s",
            schedule_expression="0 2 * * *",
            command_preview="x",
            dry_run_validated=True,
        ),
        readiness=BackupReadinessEvaluation(
            evaluation_key="e", status="passed_with_non_production_limitations"
        ),
    )
    assert flags["backup_encryption_raw_key_persisted"] is False
    assert flags["backup_real_cloud_write_performed"] is False
    assert flags["backup_production_backup_performed"] is False
    assert flags["backup_production_restore_performed"] is False
    assert flags["backup_production_schedule_enabled"] is False
    assert flags["backup_offhost_readback_verified"] is True


def test_assert_controlled_only_clean() -> None:
    assert (
        assert_controlled_only(
            backup_run=BackupRun(backup_key="b", source_database="aiagents"),
            transfer=OffhostTransferRun(status="verified", readback_verified=True),
            restore=RestoreDrillRun(restore_key="r", target_database="aiagents_restore_drill_x"),
            schedule=BackupScheduleDefinition(
                schedule_key="s", schedule_expression="0 2 * * *", command_preview="x"
            ),
        )
        == []
    )


def test_assert_controlled_only_detects_violations() -> None:
    violations = assert_controlled_only(
        backup_run=BackupRun(
            backup_key="b", source_database="db", environment="production", production_executed=True
        ),
        transfer=OffhostTransferRun(status="verified", real_cloud_write_performed=True),
        restore=RestoreDrillRun(
            restore_key="r",
            target_database="aiagents_restore_drill_x",
            production_restore_performed=True,
        ),
        schedule=BackupScheduleDefinition(
            schedule_key="s",
            schedule_expression="0 2 * * *",
            command_preview="x",
            production_schedule_enabled=True,
        ),
    )
    assert "production_backup_performed" in violations
    assert "real_cloud_write_performed" in violations
    assert "production_restore_performed" in violations
    assert "production_schedule_enabled" in violations
