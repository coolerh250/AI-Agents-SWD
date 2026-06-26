"""Step 59 -- sandbox draft PR dry-run planner.

Validates the request against the policy / allowlist / branch / metadata models and
produces a DraftPrPlan. NO side effect is performed: no branch is created, no PR is
opened, no external call is made. Shared by both dry_run and live_sandbox modes.
"""

from __future__ import annotations

from . import allowlist, branch, policy, pr_metadata
from .models import DraftPrPlan


class PlanError(ValueError):
    """Raised when the request violates policy / allowlist / branch / metadata rules."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def build_plan(
    *,
    repository_key: str,
    project_key: str,
    project_id: str,
    work_item_key: str,
    work_item_title: str,
    work_item_id: str,
    correlation_id: str,
    dispatch_id: str | None = None,
    base_branch: str | None = None,
    summary: str = "",
    mode: str = "dry_run",
) -> DraftPrPlan:
    repo = allowlist.resolve_repository(repository_key)
    if repo is None:
        raise PlanError("repository_not_allowlisted")
    if not repo.allow_draft_pr:
        raise PlanError("draft_pr_not_allowed_for_repo")

    base = base_branch or (repo.allowed_base_branches[0] if repo.allowed_base_branches else "")
    if not base or not allowlist.base_branch_allowed(repo, base):
        raise PlanError("base_branch_not_allowed")
    if base in policy.forbidden_base_branches():
        raise PlanError("base_branch_forbidden")

    head = branch.generate_branch_name(project_key, work_item_key, correlation_id)
    if not allowlist.head_prefix_allowed(repo, head):
        raise PlanError("head_branch_prefix_not_allowed")

    title = pr_metadata.build_title(project_key, work_item_title)
    body = pr_metadata.build_body(
        project_key=project_key,
        project_id=project_id,
        work_item_key=work_item_key,
        work_item_title=work_item_title,
        work_item_id=work_item_id,
        dispatch_id=dispatch_id,
        correlation_id=correlation_id,
        summary=summary or f"Sandbox draft PR for {work_item_key}.",
    )
    return DraftPrPlan(
        repository_key=repo.key,
        owner=repo.owner,
        repo=repo.repo,
        base_branch=base,
        head_branch=head,
        title=title,
        body=body,
        project_key=project_key,
        work_item_key=work_item_key,
        correlation_id=correlation_id,
        mode=mode,
    )
