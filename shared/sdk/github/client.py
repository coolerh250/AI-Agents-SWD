"""Local/test GitHub SDK.

This client supports two modes:

* ``dry_run=True`` (default) — every call returns a deterministic mock
  result and contacts no real GitHub API. Used by the platform's
  ``/github/workflow/demo-pr`` flow on 10.0.1.31.
* ``dry_run=False`` — issues real REST calls against
  ``https://api.github.com`` using ``GITHUB_TOKEN`` from the
  environment.  If the env var is missing the call raises
  :class:`GitHubMissingTokenError` *before* any network IO. The token
  is never logged or written to any artifact.

Every operation is wrapped in an OTel span and surfaces failures as
:class:`GitHubClientError` so callers can keep their own crash-free
contract.
"""

from __future__ import annotations

import base64
import hashlib
import os
from typing import Any

import httpx

from shared.sdk.github.errors import (
    GitHubAuthError,
    GitHubClientError,
    GitHubMissingTokenError,
    GitHubNotFoundError,
)
from shared.sdk.github.models import (
    GitHubBranch,
    GitHubChecks,
    GitHubFile,
    GitHubIssue,
    GitHubPullRequest,
)
from shared.sdk.observability.tracing import start_span

DEFAULT_BASE_URL = "https://api.github.com"


def _normalize_repo(repo: str) -> str:
    repo = (repo or "").strip().strip("/")
    if "/" not in repo:
        raise GitHubClientError(f"invalid repo (expected owner/repo): {repo!r}")
    return repo


def _mock_sha(*parts: str) -> str:
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()  # noqa: S324
    return digest


def _mock_issue_number(repo: str, title: str) -> int:
    digest = hashlib.sha1(f"{repo}|{title}".encode()).hexdigest()  # noqa: S324
    return int(digest[:6], 16) % 9000 + 1000


class GitHubClient:
    """HTTP client for the GitHub REST API.

    Read the token from ``GITHUB_TOKEN`` env var only — never a file, never
    a constructor arg you can accidentally pass via JSON. ``dry_run`` is
    ``True`` by default; flip it explicitly to make real calls.
    """

    def __init__(
        self,
        repo: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        dry_run: bool = True,
        timeout: float = 10.0,
        env: dict[str, str] | None = None,
    ) -> None:
        self.repo = _normalize_repo(repo)
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.dry_run = bool(dry_run)
        self.timeout = timeout
        self._env = env if env is not None else dict(os.environ)

    # ---------- token handling ------------------------------------------------

    def _token(self) -> str:
        token = self._env.get("GITHUB_TOKEN", "").strip()
        if not token:
            raise GitHubMissingTokenError(
                "GITHUB_TOKEN is not set; refusing to call GitHub API. "
                "Either set the env var or use dry_run=True.",
                operation="auth",
            )
        return token

    def has_token(self) -> bool:
        return bool(self._env.get("GITHUB_TOKEN", "").strip())

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token()}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "aiagents-swd-github-automation",
        }

    # ---------- low-level request helper -------------------------------------

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(method, url, headers=self._headers(), **kwargs)
        except httpx.HTTPError as exc:
            raise GitHubClientError(
                f"GitHub request failed: {exc.__class__.__name__}",
                operation=f"{method} {path}",
            ) from exc

        if response.status_code in (401, 403):
            raise GitHubAuthError(
                f"GitHub auth failure ({response.status_code})",
                status_code=response.status_code,
                operation=f"{method} {path}",
            )
        if response.status_code == 404:
            raise GitHubNotFoundError(
                f"GitHub resource not found ({path})",
                status_code=404,
                operation=f"{method} {path}",
            )
        if response.status_code >= 400:
            raise GitHubClientError(
                f"GitHub error {response.status_code} on {method} {path}",
                status_code=response.status_code,
                operation=f"{method} {path}",
            )
        return response

    # ---------- public API ---------------------------------------------------

    async def create_issue(
        self,
        title: str,
        body: str = "",
        *,
        task_id: str = "",
        workflow_id: str = "",
    ) -> GitHubIssue:
        with start_span(
            "github.create_issue",
            **{
                "github.repo": self.repo,
                "github.operation": "create_issue",
                "github.dry_run": str(self.dry_run).lower(),
                "task_id": task_id,
                "workflow_id": workflow_id,
            },
        ):
            if self.dry_run:
                number = _mock_issue_number(self.repo, title)
                return GitHubIssue(
                    repo=self.repo,
                    number=number,
                    title=title,
                    body=body,
                    url=f"https://github.com/{self.repo}/issues/{number}",
                    dry_run=True,
                )
            response = await self._request(
                "POST",
                f"/repos/{self.repo}/issues",
                json={"title": title, "body": body},
            )
            data = response.json()
            return GitHubIssue(
                repo=self.repo,
                number=data.get("number"),
                title=data.get("title", title),
                body=data.get("body") or "",
                url=data.get("html_url", ""),
                dry_run=False,
            )

    async def create_branch(
        self,
        branch_name: str,
        *,
        base_branch: str = "main",
        task_id: str = "",
        workflow_id: str = "",
    ) -> GitHubBranch:
        with start_span(
            "github.create_branch",
            **{
                "github.repo": self.repo,
                "github.operation": "create_branch",
                "github.dry_run": str(self.dry_run).lower(),
                "task_id": task_id,
                "workflow_id": workflow_id,
            },
        ):
            if self.dry_run:
                return GitHubBranch(
                    repo=self.repo,
                    name=branch_name,
                    sha=_mock_sha("branch", self.repo, branch_name, base_branch),
                    base_branch=base_branch,
                    dry_run=True,
                )
            # Look up base ref to get the sha to branch off
            base = await self._request("GET", f"/repos/{self.repo}/git/ref/heads/{base_branch}")
            base_sha = base.json().get("object", {}).get("sha", "")
            await self._request(
                "POST",
                f"/repos/{self.repo}/git/refs",
                json={"ref": f"refs/heads/{branch_name}", "sha": base_sha},
            )
            return GitHubBranch(
                repo=self.repo,
                name=branch_name,
                sha=base_sha,
                base_branch=base_branch,
                dry_run=False,
            )

    async def create_or_update_file(
        self,
        path: str,
        content: str,
        message: str,
        *,
        branch: str,
        task_id: str = "",
        workflow_id: str = "",
    ) -> GitHubFile:
        with start_span(
            "github.create_or_update_file",
            **{
                "github.repo": self.repo,
                "github.operation": "create_or_update_file",
                "github.dry_run": str(self.dry_run).lower(),
                "task_id": task_id,
                "workflow_id": workflow_id,
            },
        ):
            preview = content if len(content) <= 200 else content[:197] + "..."
            if self.dry_run:
                return GitHubFile(
                    repo=self.repo,
                    branch=branch,
                    path=path,
                    content_preview=preview,
                    sha=_mock_sha("file", self.repo, branch, path, message),
                    dry_run=True,
                )
            encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
            payload: dict[str, Any] = {
                "message": message,
                "content": encoded,
                "branch": branch,
            }
            # GitHub requires `sha` to update an existing file. Best-effort
            # GET; ignore 404 (file does not exist yet).
            try:
                existing = await self._request(
                    "GET",
                    f"/repos/{self.repo}/contents/{path}",
                    params={"ref": branch},
                )
                existing_sha = existing.json().get("sha")
                if existing_sha:
                    payload["sha"] = existing_sha
            except GitHubNotFoundError:
                pass
            response = await self._request(
                "PUT",
                f"/repos/{self.repo}/contents/{path}",
                json=payload,
            )
            data = response.json().get("content", {})
            return GitHubFile(
                repo=self.repo,
                branch=branch,
                path=path,
                content_preview=preview,
                sha=data.get("sha", ""),
                dry_run=False,
            )

    async def create_pull_request(
        self,
        title: str,
        body: str,
        *,
        head_branch: str,
        base_branch: str = "main",
        task_id: str = "",
        workflow_id: str = "",
    ) -> GitHubPullRequest:
        with start_span(
            "github.create_pull_request",
            **{
                "github.repo": self.repo,
                "github.operation": "create_pull_request",
                "github.dry_run": str(self.dry_run).lower(),
                "task_id": task_id,
                "workflow_id": workflow_id,
            },
        ):
            if self.dry_run:
                number = _mock_issue_number(self.repo, f"pr:{title}")
                return GitHubPullRequest(
                    repo=self.repo,
                    number=number,
                    title=title,
                    body=body,
                    base_branch=base_branch,
                    head_branch=head_branch,
                    url=f"https://github.com/{self.repo}/pull/{number}",
                    state="open",
                    dry_run=True,
                )
            response = await self._request(
                "POST",
                f"/repos/{self.repo}/pulls",
                json={
                    "title": title,
                    "body": body,
                    "head": head_branch,
                    "base": base_branch,
                },
            )
            data = response.json()
            return GitHubPullRequest(
                repo=self.repo,
                number=data.get("number"),
                title=data.get("title", title),
                body=data.get("body") or "",
                base_branch=base_branch,
                head_branch=head_branch,
                url=data.get("html_url", ""),
                state=data.get("state", "open"),
                dry_run=False,
            )

    async def get_pull_request(
        self,
        number: int,
        *,
        task_id: str = "",
        workflow_id: str = "",
    ) -> GitHubPullRequest:
        with start_span(
            "github.get_pull_request",
            **{
                "github.repo": self.repo,
                "github.operation": "get_pull_request",
                "github.dry_run": str(self.dry_run).lower(),
                "task_id": task_id,
                "workflow_id": workflow_id,
            },
        ):
            if self.dry_run:
                return GitHubPullRequest(
                    repo=self.repo,
                    number=number,
                    title=f"mock PR #{number}",
                    body="dry-run body",
                    base_branch="main",
                    head_branch=f"mock/{number}",
                    url=f"https://github.com/{self.repo}/pull/{number}",
                    state="open",
                    dry_run=True,
                )
            response = await self._request("GET", f"/repos/{self.repo}/pulls/{number}")
            data = response.json()
            return GitHubPullRequest(
                repo=self.repo,
                number=data.get("number", number),
                title=data.get("title", ""),
                body=data.get("body") or "",
                base_branch=(data.get("base") or {}).get("ref", ""),
                head_branch=(data.get("head") or {}).get("ref", ""),
                url=data.get("html_url", ""),
                state=data.get("state", "open"),
                dry_run=False,
            )

    async def read_checks(
        self,
        ref: str,
        *,
        task_id: str = "",
        workflow_id: str = "",
    ) -> GitHubChecks:
        with start_span(
            "github.read_checks",
            **{
                "github.repo": self.repo,
                "github.operation": "read_checks",
                "github.dry_run": str(self.dry_run).lower(),
                "task_id": task_id,
                "workflow_id": workflow_id,
            },
        ):
            if self.dry_run:
                return GitHubChecks(
                    repo=self.repo,
                    ref=ref,
                    checks=[
                        {"name": "build", "status": "completed", "conclusion": "success"},
                        {"name": "tests", "status": "completed", "conclusion": "success"},
                        {"name": "lint", "status": "completed", "conclusion": "success"},
                    ],
                    dry_run=True,
                )
            response = await self._request("GET", f"/repos/{self.repo}/commits/{ref}/check-runs")
            data = response.json()
            checks = [
                {
                    "name": run.get("name", ""),
                    "status": run.get("status", ""),
                    "conclusion": run.get("conclusion") or "",
                }
                for run in data.get("check_runs", [])
            ]
            return GitHubChecks(repo=self.repo, ref=ref, checks=checks, dry_run=False)

    async def list_open_pull_requests(
        self,
        *,
        task_id: str = "",
        workflow_id: str = "",
    ) -> list[GitHubPullRequest]:
        with start_span(
            "github.list_open_pull_requests",
            **{
                "github.repo": self.repo,
                "github.operation": "list_open_pull_requests",
                "github.dry_run": str(self.dry_run).lower(),
                "task_id": task_id,
                "workflow_id": workflow_id,
            },
        ):
            if self.dry_run:
                return []
            response = await self._request(
                "GET", f"/repos/{self.repo}/pulls", params={"state": "open"}
            )
            return [
                GitHubPullRequest(
                    repo=self.repo,
                    number=item.get("number"),
                    title=item.get("title", ""),
                    body=item.get("body") or "",
                    base_branch=(item.get("base") or {}).get("ref", ""),
                    head_branch=(item.get("head") or {}).get("ref", ""),
                    url=item.get("html_url", ""),
                    state=item.get("state", "open"),
                    dry_run=False,
                )
                for item in response.json()
            ]
