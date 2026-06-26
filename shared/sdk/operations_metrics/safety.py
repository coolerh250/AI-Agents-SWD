"""Step 58 -- Admin Console v2 operational metrics safety fields (config-driven)."""

from __future__ import annotations

from typing import Any


def operational_metrics_safety_fields() -> dict[str, Any]:
    """Visibility-only metrics capability; every side-effect/production toggle is off."""
    return {
        "admin_console_v2_metrics_enabled": True,
        "operational_metrics_snapshot_generated": True,
        "operational_metrics_external_side_effect_enabled": False,
        "operational_metrics_gitops_sync_enabled": False,
        "operational_metrics_kubernetes_mutation_enabled": False,
        "operational_metrics_github_write_enabled": False,
        "operational_metrics_external_send_enabled": False,
        "operational_metrics_production_action_enabled": False,
        "operational_metrics_production_ready": False,
    }
