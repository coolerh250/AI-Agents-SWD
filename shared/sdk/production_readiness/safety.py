"""Step 62 -- production readiness safety fields (config-driven).

Read straight from the committed policy + models so the dangerous toggles (production
deploy / sync / merge / image push / restore / failover / rollout execution) and
productionReady / productionApproved / production-action-allowed cannot drift true. No
production action is ever taken; the executed counts are 0.
"""

from __future__ import annotations

from typing import Any

from . import blocking_rules, policy, prerequisites


def production_readiness_safety_fields(
    *,
    production_deployment_executed_count: int = 0,
    production_sync_executed_count: int = 0,
    production_restore_executed_count: int = 0,
    production_failover_executed_count: int = 0,
) -> dict[str, Any]:
    p = policy.load_policy()
    results = blocking_rules.evaluate()
    blocker_count = sum(1 for r in results if r.active)
    missing_prereq_count = len(prerequisites.missing_prerequisites())
    return {
        "production_readiness_gate_enabled": bool(p.get("enabled", False)),
        "production_readiness_gate_report_generated": True,
        "production_readiness_gate_production_ready": bool(p.get("productionReady", False)),
        "production_readiness_gate_production_approved": False,
        "production_readiness_gate_allows_production_action": bool(
            p.get("currentStageAllowsProductionAction", False)
        ),
        "production_readiness_gate_allows_deploy": bool(p.get("allowProductionDeploy", False)),
        "production_readiness_gate_allows_sync": bool(p.get("allowProductionSync", False)),
        "production_readiness_gate_allows_merge": bool(p.get("allowGitHubMerge", False)),
        "production_readiness_gate_allows_image_push": bool(p.get("allowImagePush", False)),
        "production_readiness_gate_allows_restore": bool(p.get("allowProductionRestore", False)),
        "production_readiness_gate_allows_failover": bool(p.get("allowProductionFailover", False)),
        "production_readiness_operator_review_enabled": True,
        "production_readiness_operator_review_is_approval": False,
        "production_readiness_missing_prerequisite_count": int(missing_prereq_count),
        "production_readiness_blocker_count": int(blocker_count),
        "production_rollout_execution_enabled": False,
        "production_deployment_executed_count": int(production_deployment_executed_count),
        "production_sync_executed_count": int(production_sync_executed_count),
        "production_restore_executed_count": int(production_restore_executed_count),
        "production_failover_executed_count": int(production_failover_executed_count),
    }
