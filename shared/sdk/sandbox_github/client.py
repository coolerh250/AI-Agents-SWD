"""Step 59 -- sandbox GitHub client (dry_run + optional live_sandbox).

Orchestrates the controlled draft-PR flow. dry_run produces a validated plan with NO
side effect. live_sandbox -- only when explicitly enabled AND a credential is present
AND the repo is allowlisted -- creates a sandbox branch + a *draft* PR via the GitHub
REST API. There is deliberately NO merge / ready-for-review / workflow-dispatch /
issue-write / release / deployment capability. The token is read from the environment
only and never logged or returned.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from . import audit, policy
from .dry_run import PlanError, build_plan
from .models import MODE_DRY_RUN, MODE_LIVE_SANDBOX, DraftPrPlan, DraftPrResult

_GITHUB_API = "https://api.github.com"


class SandboxGitHubClient:
    """Sandbox-only draft PR client. Live calls are gated by policy + credential."""

    def __init__(self, *, actor: str, role: str, reason: str) -> None:
        self.actor = actor
        self.role = role
        self.reason = reason

    def _audit(
        self,
        event_type: str,
        *,
        project_id: str | None,
        work_item_id: str | None,
        repository_key: str,
        mode: str,
        correlation_id: str,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return audit.build_audit_metadata(
            event_type=event_type,
            actor=self.actor,
            role=self.role,
            reason=self.reason,
            project_id=project_id,
            work_item_id=work_item_id,
            repository_key=repository_key,
            mode=mode,
            correlation_id=correlation_id,
            extra=extra,
        )

    def request_draft_pr(
        self,
        *,
        repository_key: str,
        project_id: str,
        project_key: str,
        work_item_id: str,
        work_item_key: str,
        work_item_title: str,
        correlation_id: str,
        dispatch_id: str | None = None,
        base_branch: str | None = None,
        summary: str = "",
        requested_mode: str | None = None,
        production_effect: bool = False,
    ) -> DraftPrResult:
        events: list[dict[str, Any]] = []
        mode, blocked = policy.resolve_mode(requested_mode)

        events.append(
            self._audit(
                "sandbox_github_draft_pr_requested",
                project_id=project_id,
                work_item_id=work_item_id,
                repository_key=repository_key,
                mode=mode,
                correlation_id=correlation_id,
            )
        )

        # A production-effect work item never creates a PR directly.
        if production_effect:
            events.append(
                self._audit(
                    "sandbox_github_draft_pr_blocked",
                    project_id=project_id,
                    work_item_id=work_item_id,
                    repository_key=repository_key,
                    mode=mode,
                    correlation_id=correlation_id,
                    extra={"block_reason": "production_effect_requires_approval"},
                )
            )
            return DraftPrResult(
                status="blocked",
                mode=mode,
                repository_key=repository_key,
                project_id=project_id,
                work_item_id=work_item_id,
                correlation_id=correlation_id,
                reason="production_effect_requires_approval",
                audit_events=events,
            )

        # Validate against policy / allowlist / branch / metadata -> a plan.
        try:
            plan = build_plan(
                repository_key=repository_key,
                project_key=project_key,
                project_id=project_id,
                work_item_key=work_item_key,
                work_item_title=work_item_title,
                work_item_id=work_item_id,
                correlation_id=correlation_id,
                dispatch_id=dispatch_id,
                base_branch=base_branch,
                summary=summary,
                mode=mode,
            )
        except PlanError as exc:
            events.append(
                self._audit(
                    "sandbox_github_draft_pr_blocked",
                    project_id=project_id,
                    work_item_id=work_item_id,
                    repository_key=repository_key,
                    mode=mode,
                    correlation_id=correlation_id,
                    extra={"block_reason": exc.reason},
                )
            )
            return DraftPrResult(
                status="blocked",
                mode=mode,
                repository_key=repository_key,
                project_id=project_id,
                work_item_id=work_item_id,
                correlation_id=correlation_id,
                reason=exc.reason,
                audit_events=events,
            )

        events.append(
            self._audit(
                "sandbox_github_draft_pr_policy_checked",
                project_id=project_id,
                work_item_id=work_item_id,
                repository_key=repository_key,
                mode=mode,
                correlation_id=correlation_id,
                extra={"head_branch": plan.head_branch, "base_branch": plan.base_branch},
            )
        )

        # live_sandbox blocked (not enabled / no credential / not allowed) -> stop in a
        # blocked state. Never fabricate a live success.
        if mode == MODE_LIVE_SANDBOX and blocked is not None:
            events.append(
                self._audit(
                    "sandbox_github_draft_pr_blocked",
                    project_id=project_id,
                    work_item_id=work_item_id,
                    repository_key=repository_key,
                    mode=mode,
                    correlation_id=correlation_id,
                    extra={"block_reason": blocked},
                )
            )
            return DraftPrResult(
                status="blocked",
                mode=mode,
                repository_key=repository_key,
                project_id=project_id,
                work_item_id=work_item_id,
                correlation_id=correlation_id,
                branch_name=plan.head_branch,
                reason=blocked,
                plan=plan.to_dict(),
                audit_events=events,
            )

        if mode == MODE_DRY_RUN:
            return DraftPrResult(
                status="planned",
                mode=MODE_DRY_RUN,
                repository_key=repository_key,
                project_id=project_id,
                work_item_id=work_item_id,
                correlation_id=correlation_id,
                branch_name=plan.head_branch,
                plan=plan.to_dict(),
                audit_events=events,
            )

        # live_sandbox: create branch + draft PR via the GitHub API.
        return self._create_live(plan, project_id, work_item_id, events)

    # -- live sandbox ------------------------------------------------------------
    def _gh(self, method: str, path: str, body: dict | None = None) -> dict[str, Any]:
        token = os.environ.get(policy.TOKEN_ENV, "").strip()
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(_GITHUB_API + path, data=data, method=method)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310
            return json.loads(r.read().decode("utf-8"))

    def _create_live(
        self,
        plan: DraftPrPlan,
        project_id: str,
        work_item_id: str,
        events: list[dict[str, Any]],
    ) -> DraftPrResult:
        try:
            ref = self._gh(
                "GET", f"/repos/{plan.owner}/{plan.repo}/git/ref/heads/{plan.base_branch}"
            )
            base_sha = ref["object"]["sha"]
            self._gh(
                "POST",
                f"/repos/{plan.owner}/{plan.repo}/git/refs",
                {"ref": f"refs/heads/{plan.head_branch}", "sha": base_sha},
            )
            events.append(
                self._audit(
                    "sandbox_github_draft_branch_created",
                    project_id=project_id,
                    work_item_id=work_item_id,
                    repository_key=plan.repository_key,
                    mode=MODE_LIVE_SANDBOX,
                    correlation_id=plan.correlation_id,
                    extra={"head_branch": plan.head_branch},
                )
            )
            pr = self._gh(
                "POST",
                f"/repos/{plan.owner}/{plan.repo}/pulls",
                {
                    "title": plan.title,
                    "head": plan.head_branch,
                    "base": plan.base_branch,
                    "body": plan.body,
                    "draft": True,  # never ready-for-review
                },
            )
            events.append(
                self._audit(
                    "sandbox_github_draft_pr_created",
                    project_id=project_id,
                    work_item_id=work_item_id,
                    repository_key=plan.repository_key,
                    mode=MODE_LIVE_SANDBOX,
                    correlation_id=plan.correlation_id,
                    extra={"draft_pr_number": pr.get("number")},
                )
            )
            return DraftPrResult(
                status="created",
                mode=MODE_LIVE_SANDBOX,
                repository_key=plan.repository_key,
                project_id=project_id,
                work_item_id=work_item_id,
                correlation_id=plan.correlation_id,
                branch_name=plan.head_branch,
                draft_pr_url=pr.get("html_url"),
                draft_pr_number=pr.get("number"),
                plan=plan.to_dict(),
                audit_events=events,
            )
        except (urllib.error.URLError, OSError, KeyError, ValueError) as exc:
            events.append(
                self._audit(
                    "sandbox_github_draft_pr_failed",
                    project_id=project_id,
                    work_item_id=work_item_id,
                    repository_key=plan.repository_key,
                    mode=MODE_LIVE_SANDBOX,
                    correlation_id=plan.correlation_id,
                    extra={"failure": type(exc).__name__},
                )
            )
            return DraftPrResult(
                status="failed",
                mode=MODE_LIVE_SANDBOX,
                repository_key=plan.repository_key,
                project_id=project_id,
                work_item_id=work_item_id,
                correlation_id=plan.correlation_id,
                branch_name=plan.head_branch,
                reason=f"live_sandbox_error:{type(exc).__name__}",
                plan=plan.to_dict(),
                audit_events=events,
            )
