"""Step 63A -- controlled rollout go/no-go recommendation evaluation.

The recommendation is NEVER an approval and NEVER authorizes a production action. A missing
production target / credentials / GitOps / approval channel forces no_go. Incomplete
rollback / DR caps at conditional_go. The gate never auto-promotes to ``go``; ``go`` would
require all evidence present and is still not an approval.
"""

from __future__ import annotations

from typing import Any

from . import loaders
from .models import REC_CONDITIONAL_GO, REC_NO_GO


def evaluate() -> dict[str, Any]:
    target = loaders.missing_target_items()
    creds = loaders.missing_credential_refs()
    gitops = loaders.missing_gitops_items()
    approval = loaders.missing_approval_items()
    rollback_dr_incomplete = loaders.rollback_dr_incomplete()

    no_go_reasons: list[str] = []
    if target:
        no_go_reasons.append("production_target_missing")
    if creds:
        no_go_reasons.append("production_credentials_missing")
    if gitops:
        no_go_reasons.append("production_gitops_missing")
    if approval:
        no_go_reasons.append("production_approval_channel_missing")

    if no_go_reasons:
        recommendation = REC_NO_GO
    elif rollback_dr_incomplete:
        recommendation = REC_CONDITIONAL_GO
    else:
        # All hard gates satisfied + rollback/DR complete: the most this review can yield is
        # conditional_go pending explicit operator approval. It is never an approval.
        recommendation = REC_CONDITIONAL_GO

    return {
        "recommendation": recommendation,
        "recommendation_is_approval": False,
        "authorizes_production_action": False,
        "production_ready": False,
        "production_approved": False,
        "no_go_reasons": no_go_reasons,
        "missing_target_count": len(target),
        "missing_credential_count": len(creds),
        "missing_gitops_count": len(gitops),
        "missing_approval_channel_count": len(approval),
        "rollback_dr_incomplete": rollback_dr_incomplete,
    }
