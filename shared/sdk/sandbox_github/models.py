"""Step 59 -- sandbox GitHub draft PR data models + mode constants."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

MODE_DRY_RUN = "dry_run"
MODE_LIVE_SANDBOX = "live_sandbox"
ALLOWED_MODES = (MODE_DRY_RUN, MODE_LIVE_SANDBOX)


@dataclass(frozen=True)
class SandboxRepo:
    key: str
    owner: str
    repo: str
    allowed: bool
    sandbox_only: bool
    allowed_base_branches: tuple[str, ...]
    allowed_head_prefixes: tuple[str, ...]
    allow_draft_pr: bool
    allow_merge: bool
    allow_ready_for_review: bool
    allow_release: bool
    allow_deployment: bool
    allow_workflow_dispatch: bool


@dataclass
class DraftPrPlan:
    """A dry-run plan -- the intended draft PR with NO side effect performed."""

    repository_key: str
    owner: str
    repo: str
    base_branch: str
    head_branch: str
    title: str
    body: str
    project_key: str
    work_item_key: str
    correlation_id: str
    mode: str = MODE_DRY_RUN

    def to_dict(self) -> dict[str, Any]:
        return {
            "repository_key": self.repository_key,
            "owner": self.owner,
            "repo": self.repo,
            "base_branch": self.base_branch,
            "head_branch": self.head_branch,
            "title": self.title,
            "body": self.body,
            "project_key": self.project_key,
            "work_item_key": self.work_item_key,
            "correlation_id": self.correlation_id,
            "mode": self.mode,
            "draft": True,
            "ready_for_review": False,
            "production_executed": False,
        }


@dataclass
class DraftPrResult:
    """Outcome of a sandbox draft PR request (dry_run or live_sandbox)."""

    status: str  # planned | blocked | created | failed
    mode: str
    repository_key: str
    project_id: str | None = None
    work_item_id: str | None = None
    correlation_id: str | None = None
    branch_name: str | None = None
    draft_pr_url: str | None = None
    draft_pr_number: int | None = None
    reason: str | None = None
    plan: dict[str, Any] | None = None
    audit_events: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "mode": self.mode,
            "repository_key": self.repository_key,
            "project_id": self.project_id,
            "work_item_id": self.work_item_id,
            "correlation_id": self.correlation_id,
            "branch_name": self.branch_name,
            "draft_pr_url": self.draft_pr_url,
            "draft_pr_number": self.draft_pr_number,
            "reason": self.reason,
            "plan": self.plan,
            "production_executed": False,
            "merge_performed": False,
            "ready_for_review_performed": False,
            "workflow_dispatch_performed": False,
            "non_sandbox_repo_write_performed": False,
        }
