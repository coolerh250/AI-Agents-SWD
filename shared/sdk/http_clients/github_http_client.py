"""HTTP client for the github-automation service.

This is the in-cluster client other services (e.g. communication-gateway)
use to reach github-automation. The actual GitHub-side calls happen
inside the github-automation service via :mod:`shared.sdk.github`; this
file is just an httpx wrapper around the FastAPI endpoints.
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
