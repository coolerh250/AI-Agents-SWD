"""Step 59 -- sandbox GitHub draft PR safety fields.

Config-driven from the committed policy (no DB, no cluster, no GitHub call). The
dangerous toggles read straight from the policy so they cannot silently drift true.
The token is never read here; only its presence governs live-mode effectiveness.
"""

from __future__ import annotations

from typing import Any

from . import policy
from .models import MODE_DRY_RUN


def sandbox_github_safety_fields(*, draft_pr_created_count: int = 0) -> dict[str, Any]:
    p = policy.load_policy()
    live_effective = policy.live_mode_effective()
    return {
        "sandbox_github_draft_pr_enabled": bool(p.get("enabled", False)),
        "sandbox_github_draft_pr_live_mode_enabled": bool(live_effective),
        "sandbox_github_draft_pr_default_mode": str(p.get("defaultMode", MODE_DRY_RUN)),
        "sandbox_github_repository_allowlist_enabled": True,
        "sandbox_github_arbitrary_repo_allowed": bool(p.get("allowNonSandboxRepo", False)),
        "sandbox_github_merge_enabled": bool(p.get("allowMerge", False)),
        "sandbox_github_ready_for_review_enabled": bool(p.get("allowReadyForReview", False)),
        "sandbox_github_workflow_dispatch_enabled": bool(p.get("allowWorkflowDispatch", False)),
        "sandbox_github_issue_write_enabled": bool(p.get("allowIssueWrite", False)),
        "sandbox_github_release_write_enabled": bool(p.get("allowReleaseWrite", False)),
        "sandbox_github_deployment_write_enabled": bool(p.get("allowDeploymentWrite", False)),
        "sandbox_github_token_exposed": False,
        "sandbox_github_production_branch_allowed": bool(p.get("allowProductionBranch", False)),
        "sandbox_github_non_sandbox_repo_write_performed": False,
        "sandbox_github_draft_pr_created_count": int(draft_pr_created_count),
        "sandbox_github_production_ready": bool(p.get("productionReady", False)),
    }
