"""Step 61 -- backup / restore / DR safety fields."""

from __future__ import annotations

from shared.sdk.backup_restore_dr import backup_restore_dr_safety_fields


def test_enabled_flags_true() -> None:
    sf = backup_restore_dr_safety_fields()
    for k in (
        "backup_restore_dr_enabled",
        "backup_inventory_enabled",
        "controlled_cleanup_review_enabled",
        "restore_plan_enabled",
        "restore_validation_enabled",
        "recovery_evidence_enabled",
    ):
        assert sf[k] is True, k


def test_dangerous_toggles_false() -> None:
    sf = backup_restore_dr_safety_fields()
    for k in (
        "backup_restore_dr_production_ready",
        "backup_restore_dr_allow_production_restore",
        "backup_restore_dr_allow_production_failover",
        "backup_restore_dr_allow_external_backup_upload",
        "backup_restore_dr_allow_cloud_provider_write",
        "backup_restore_dr_allow_argocd_production_sync",
        "backup_restore_dr_allow_kubernetes_production_mutation",
        "cleanup_execution_enabled",
        "restore_execution_enabled",
        "cleanup_teardown_kind_enabled",
        "cleanup_teardown_argocd_enabled",
    ):
        assert sf[k] is False, k


def test_production_counts_zero() -> None:
    sf = backup_restore_dr_safety_fields()
    for k in (
        "production_restore_plan_count",
        "production_failover_plan_count",
        "production_restore_executed_count",
        "production_failover_executed_count",
    ):
        assert sf[k] == 0, k
