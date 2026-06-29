"""Step 60 -- release governance safety fields (config-driven).

Read straight from the committed policy so the dangerous toggles (production deploy /
auto-promotion / merge / sync / image push / registry login) cannot drift true. No DB,
no cluster, no deploy. Production counts are 0 (no production target is ever accepted).
"""

from __future__ import annotations

from typing import Any

from . import policy


def release_governance_safety_fields(
    *,
    release_candidate_production_ready_count: int = 0,
    deployment_intent_production_target_count: int = 0,
    deployment_intent_production_executed_count: int = 0,
) -> dict[str, Any]:
    p = policy.load_policy()
    return {
        "release_governance_enabled": bool(p.get("enabled", False)),
        "release_candidate_enabled": True,
        "deployment_intent_enabled": True,
        "release_governance_production_ready": bool(p.get("productionReady", False)),
        "release_governance_allow_production_deploy": bool(p.get("allowProductionDeploy", False)),
        "release_governance_allow_auto_promotion": bool(p.get("allowAutoPromotion", False)),
        "release_governance_allow_github_merge": bool(p.get("allowGitHubMerge", False)),
        "release_governance_allow_argocd_production_sync": bool(
            p.get("allowArgoCDProductionSync", False)
        ),
        "release_governance_allow_image_push": bool(p.get("allowImagePush", False)),
        "release_governance_allow_registry_login": bool(p.get("allowRegistryLogin", False)),
        "release_candidate_production_ready_count": int(release_candidate_production_ready_count),
        "deployment_intent_production_target_count": int(deployment_intent_production_target_count),
        "deployment_intent_production_executed_count": int(
            deployment_intent_production_executed_count
        ),
    }
