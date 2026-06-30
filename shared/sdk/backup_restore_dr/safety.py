"""Step 61 -- backup / restore / DR safety fields (config-driven).

Read straight from the committed policy so the dangerous toggles (production restore /
production failover / external upload / cloud write / cleanup execution / restore execution
/ kind+ArgoCD teardown) cannot drift true. No DB, no cluster, no restore. Production counts
are 0 (no production restore plan / failover is ever accepted).
"""

from __future__ import annotations

from typing import Any

from . import policy


def backup_restore_dr_safety_fields(
    *,
    production_restore_plan_count: int = 0,
    production_failover_plan_count: int = 0,
    production_restore_executed_count: int = 0,
    production_failover_executed_count: int = 0,
) -> dict[str, Any]:
    p = policy.load_policy()
    return {
        "backup_restore_dr_enabled": bool(p.get("enabled", False)),
        "backup_inventory_enabled": True,
        "controlled_cleanup_review_enabled": True,
        "restore_plan_enabled": True,
        "restore_validation_enabled": True,
        "recovery_evidence_enabled": True,
        "backup_restore_dr_production_ready": bool(p.get("productionReady", False)),
        "backup_restore_dr_allow_production_restore": bool(p.get("allowProductionRestore", False)),
        "backup_restore_dr_allow_production_failover": bool(
            p.get("allowProductionFailover", False)
        ),
        "backup_restore_dr_allow_external_backup_upload": bool(
            p.get("allowExternalBackupUpload", False)
        ),
        "backup_restore_dr_allow_cloud_provider_write": bool(
            p.get("allowCloudProviderWrite", False)
        ),
        "backup_restore_dr_allow_argocd_production_sync": bool(
            p.get("allowArgoCDProductionSync", False)
        ),
        "backup_restore_dr_allow_kubernetes_production_mutation": bool(
            p.get("allowKubernetesProductionMutation", False)
        ),
        "cleanup_execution_enabled": bool(p.get("allowCleanupExecution", False)),
        "restore_execution_enabled": bool(p.get("allowRestoreExecution", False)),
        "cleanup_teardown_kind_enabled": bool(p.get("allowKindTeardown", False)),
        "cleanup_teardown_argocd_enabled": bool(p.get("allowArgoCDTeardown", False)),
        "production_restore_plan_count": int(production_restore_plan_count),
        "production_failover_plan_count": int(production_failover_plan_count),
        "production_restore_executed_count": int(production_restore_executed_count),
        "production_failover_executed_count": int(production_failover_executed_count),
    }
