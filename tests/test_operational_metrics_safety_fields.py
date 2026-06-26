"""Step 58 -- operational metrics safety fields (config-driven)."""

from __future__ import annotations

from shared.sdk.operations_metrics import operational_metrics_safety_fields


def test_metrics_enabled_no_side_effects() -> None:
    f = operational_metrics_safety_fields()
    assert f["admin_console_v2_metrics_enabled"] is True
    assert f["operational_metrics_snapshot_generated"] is True


def test_all_side_effect_and_production_toggles_off() -> None:
    f = operational_metrics_safety_fields()
    for key in (
        "operational_metrics_external_side_effect_enabled",
        "operational_metrics_gitops_sync_enabled",
        "operational_metrics_kubernetes_mutation_enabled",
        "operational_metrics_github_write_enabled",
        "operational_metrics_external_send_enabled",
        "operational_metrics_production_action_enabled",
        "operational_metrics_production_ready",
    ):
        assert f[key] is False, key
