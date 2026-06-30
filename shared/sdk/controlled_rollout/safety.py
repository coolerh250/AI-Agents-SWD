"""Step 63A -- controlled rollout review safety fields (config-driven).

Read straight from the committed review policy + models so the dangerous toggles
(production deploy / sync / merge / image push / restore / failover / action) and
recommendation-is-approval cannot drift true. No production action is ever taken; the
production-action executed count is 0. The recommendation reflects the live gap analysis
(no_go while the production target / credentials / GitOps / approval channel are missing).
"""

from __future__ import annotations

from typing import Any

from . import loaders, recommendation


def controlled_rollout_safety_fields(
    *,
    controlled_rollout_production_action_executed_count: int = 0,
) -> dict[str, Any]:
    p = loaders.load("policy")
    rec = recommendation.evaluate()
    return {
        "controlled_rollout_review_enabled": bool(p.get("enabled", False)),
        "controlled_rollout_review_report_generated": True,
        "controlled_rollout_recommendation": rec["recommendation"],
        "controlled_rollout_recommendation_is_approval": False,
        "controlled_rollout_allows_production_action": bool(p.get("allowsProductionAction", False)),
        "controlled_rollout_allows_deploy": bool(p.get("allowsProductionDeploy", False)),
        "controlled_rollout_allows_sync": bool(p.get("allowsProductionSync", False)),
        "controlled_rollout_allows_merge": bool(p.get("allowsGitHubMerge", False)),
        "controlled_rollout_allows_image_push": bool(p.get("allowsImagePush", False)),
        "controlled_rollout_allows_restore": bool(p.get("allowsProductionRestore", False)),
        "controlled_rollout_allows_failover": bool(p.get("allowsProductionFailover", False)),
        "controlled_rollout_operator_review_enabled": bool(
            p.get("allowsOperatorReviewRequest", False)
        ),
        "controlled_rollout_operator_review_is_approval": bool(
            p.get("operatorReviewIsApproval", False)
        ),
        "controlled_rollout_missing_target_count": rec["missing_target_count"],
        "controlled_rollout_missing_credential_count": rec["missing_credential_count"],
        "controlled_rollout_missing_gitops_count": rec["missing_gitops_count"],
        "controlled_rollout_missing_approval_channel_count": rec["missing_approval_channel_count"],
        "controlled_rollout_production_action_executed_count": int(
            controlled_rollout_production_action_executed_count
        ),
    }
