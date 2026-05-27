"""HTTP client for the github-automation service.

This is the in-cluster client other services (e.g. communication-gateway,
devops-agent) use to reach github-automation. The actual GitHub-side calls
happen inside the github-automation service via :mod:`shared.sdk.github`;
this file is just an httpx wrapper around the FastAPI endpoints.

``run_demo_pr`` is the safe entry point for agents: any HTTP / connection
error turns into a deterministic ``status=failed`` envelope with the
``dry_run`` flag preserved, so the agent consumer loop never crashes when
github-automation is unhealthy.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from shared.sdk.observability.tracing import start_span

DEFAULT_GITHUB_AUTOMATION_URL = "http://localhost:8005"


class GitHubAutomationHttpClient:
    """HTTP client for the github-automation FastAPI service."""

    def __init__(self, base_url: str | None = None, timeout: float = 15.0) -> None:
        resolved = base_url or os.environ.get(
            "GITHUB_AUTOMATION_URL", DEFAULT_GITHUB_AUTOMATION_URL
        )
        self.base_url = resolved.rstrip("/")
        self.timeout = timeout

    async def demo_pr(
        self,
        payload: dict[str, Any],
        *,
        task_id: str = "",
        workflow_id: str = "",
    ) -> dict:
        with start_span(
            "github_automation.demo_pr",
            **{
                "http.client.service": "github-automation",
                "github.operation": "demo_pr",
                "task_id": task_id,
                "workflow_id": workflow_id,
            },
        ):
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/github/workflow/demo-pr", json=payload
                )
                response.raise_for_status()
                return response.json()

    async def run_demo_pr(
        self,
        payload: dict[str, Any],
        *,
        task_id: str = "",
        workflow_id: str = "",
    ) -> dict:
        """Call /github/workflow/demo-pr and normalise the result.

        Returns a dict with at least ``status``, ``dry_run``, ``pr_url``,
        ``issue_url``, ``branch``, ``checks_status`` keys. On HTTP/connection
        failure the status is ``failed``, the original ``dry_run`` request
        intent is preserved, and an ``error`` field carries the cause —
        agents call this method instead of ``demo_pr`` so they never crash
        when github-automation is unhealthy.
        """
        requested_dry_run = bool(payload.get("dry_run", True))
        try:
            body = await self.demo_pr(payload, task_id=task_id, workflow_id=workflow_id)
        except httpx.HTTPError as exc:
            return _safe_failure(
                requested_dry_run, payload, f"http error: {exc.__class__.__name__}"
            )
        except Exception as exc:  # any other error funnels into the safe envelope
            return _safe_failure(requested_dry_run, payload, f"{exc.__class__.__name__}: {exc}")
        return _normalize_demo_pr(body, requested_dry_run, payload)

    async def get_health(self) -> dict:
        """Return the service health envelope, or ``status=failed`` on error."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/health")
                response.raise_for_status()
                body = response.json()
                body.setdefault("status", "ok")
                return body
        except Exception as exc:
            return {"status": "failed", "error": f"{exc.__class__.__name__}: {exc}"}

    async def get_pull_request(
        self,
        number: int,
        *,
        repo: str | None = None,
        dry_run: bool = True,
        task_id: str = "",
        workflow_id: str = "",
    ) -> dict:
        with start_span(
            "github_automation.get_pull_request",
            **{
                "http.client.service": "github-automation",
                "github.operation": "get_pull_request",
                "task_id": task_id,
                "workflow_id": workflow_id,
            },
        ):
            params: dict[str, Any] = {"dry_run": dry_run}
            if repo:
                params["repo"] = repo
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/github/pull-request/{number}", params=params
                )
                response.raise_for_status()
                return response.json()

    async def get_checks(
        self,
        ref: str,
        *,
        repo: str | None = None,
        dry_run: bool = True,
        task_id: str = "",
        workflow_id: str = "",
    ) -> dict:
        with start_span(
            "github_automation.get_checks",
            **{
                "http.client.service": "github-automation",
                "github.operation": "get_checks",
                "task_id": task_id,
                "workflow_id": workflow_id,
            },
        ):
            params: dict[str, Any] = {"ref": ref, "dry_run": dry_run}
            if repo:
                params["repo"] = repo
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/github/checks", params=params)
                response.raise_for_status()
                return response.json()

    async def read_checks(
        self,
        ref: str,
        *,
        repo: str | None = None,
        dry_run: bool = True,
        task_id: str = "",
        workflow_id: str = "",
    ) -> dict:
        """Alias for :meth:`get_checks` matching the SDK naming convention."""
        return await self.get_checks(
            ref,
            repo=repo,
            dry_run=dry_run,
            task_id=task_id,
            workflow_id=workflow_id,
        )


def _safe_failure(dry_run: bool, payload: dict[str, Any], error: str) -> dict:
    return {
        "status": "failed",
        "dry_run": dry_run,
        "error": error,
        "issue_url": "",
        "branch": str(payload.get("branch_name", "")),
        "pr_url": "",
        "checks_status": "unknown",
        "event_type": "github.pr.failed",
    }


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _normalize_demo_pr(body: dict, dry_run: bool, payload: dict[str, Any]) -> dict:
    """Reduce the full demo-pr response to the slim envelope agents persist."""
    issue = _as_dict(body.get("issue"))
    branch = _as_dict(body.get("branch"))
    pr = _as_dict(body.get("pull_request"))
    checks = _as_dict(body.get("checks"))
    checks_list = checks.get("checks") if isinstance(checks.get("checks"), list) else []
    if checks_list and all(c.get("conclusion") == "success" for c in checks_list):
        checks_status = "success"
    elif checks_list:
        checks_status = "mixed"
    else:
        checks_status = "unknown"
    return {
        "status": "success",
        "dry_run": bool(body.get("dry_run", dry_run)),
        "issue_url": issue.get("url", ""),
        "branch": branch.get("name") or str(payload.get("branch_name", "")),
        "pr_url": pr.get("url", ""),
        "pr_number": pr.get("number"),
        "checks_status": checks_status,
        "event_type": body.get(
            "event_type", "github.pr.dry_run" if dry_run else "github.pr.created"
        ),
    }
