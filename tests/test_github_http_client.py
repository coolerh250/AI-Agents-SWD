"""Unit tests for shared.sdk.http_clients.github_http_client.

We don't run a real github-automation service here — we monkey-patch
``httpx.AsyncClient`` so ``run_demo_pr`` produces deterministic output
without leaving the test process. The contract under test is:

* ``run_demo_pr`` returns ``status="success"`` with a flat envelope on a
  happy-path response.
* ``run_demo_pr`` returns ``status="failed"`` with ``error`` and the
  caller's requested ``dry_run`` preserved when the HTTP call fails.
* ``get_health`` does the same safe-fail dance.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from shared.sdk.http_clients.github_http_client import GitHubAutomationHttpClient


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _success_body() -> dict:
    return {
        "dry_run": True,
        "event_type": "github.pr.dry_run",
        "issue": {"url": "https://github.com/owner/repo/issues/1"},
        "branch": {"name": "ai-agents/t1", "sha": "deadbeef"},
        "file": {"path": "docs/x.md"},
        "pull_request": {
            "number": 99,
            "url": "https://github.com/owner/repo/pull/99",
            "state": "open",
        },
        "checks": {
            "ref": "ai-agents/t1",
            "checks": [
                {"name": "build", "status": "completed", "conclusion": "success"},
                {"name": "tests", "status": "completed", "conclusion": "success"},
            ],
            "dry_run": True,
        },
    }


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(f"status {self.status_code}", request=None, response=None)


class _FakeAsyncClient:
    """Drop-in replacement for httpx.AsyncClient that returns a canned response.

    The constructor accepts arbitrary kwargs (``timeout=...``) so the wrapper
    in ``github_http_client.py`` can build it without changes.
    """

    last_request: dict[str, Any] = {}

    def __init__(self, *args: Any, response: _FakeResponse | None = None, **kwargs: Any) -> None:
        self._response = response

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def post(self, url: str, json: dict | None = None) -> _FakeResponse:
        _FakeAsyncClient.last_request = {"method": "POST", "url": url, "json": json}
        assert self._response is not None
        return self._response

    async def get(self, url: str, params: dict | None = None) -> _FakeResponse:
        _FakeAsyncClient.last_request = {"method": "GET", "url": url, "params": params}
        assert self._response is not None
        return self._response


def _patch_httpx(monkeypatch, response: _FakeResponse) -> None:
    def _factory(*args: Any, **kwargs: Any) -> _FakeAsyncClient:
        return _FakeAsyncClient(response=response)

    monkeypatch.setattr(httpx, "AsyncClient", _factory)


def test_run_demo_pr_normalises_success(monkeypatch):
    _patch_httpx(monkeypatch, _FakeResponse(200, _success_body()))
    client = GitHubAutomationHttpClient(base_url="http://github-automation:8005")
    body = {
        "task_id": "t1",
        "workflow_id": "wf-t1",
        "repo": "owner/repo",
        "branch_name": "ai-agents/t1",
        "dry_run": True,
    }
    result = _run(client.run_demo_pr(body, task_id="t1", workflow_id="wf-t1"))
    assert result["status"] == "success"
    assert result["dry_run"] is True
    assert result["pr_url"] == "https://github.com/owner/repo/pull/99"
    assert result["pr_number"] == 99
    assert result["issue_url"] == "https://github.com/owner/repo/issues/1"
    assert result["branch"] == "ai-agents/t1"
    assert result["checks_status"] == "success"
    assert result["event_type"] == "github.pr.dry_run"


def test_run_demo_pr_safe_failure_preserves_dry_run(monkeypatch):
    def _factory(*args: Any, **kwargs: Any) -> _FakeAsyncClient:
        # Raise the moment AsyncClient is used; the wrapper catches it and
        # returns the safe-failure envelope.
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "AsyncClient", _factory)
    client = GitHubAutomationHttpClient(base_url="http://nowhere:1")
    payload = {"task_id": "t2", "branch_name": "ai-agents/t2", "dry_run": True}
    result = _run(client.run_demo_pr(payload))
    assert result["status"] == "failed"
    assert result["dry_run"] is True
    assert result["pr_url"] == ""
    assert result["branch"] == "ai-agents/t2"
    assert "ConnectError" in result["error"] or "http error" in result["error"]
    assert result["event_type"] == "github.pr.failed"


def test_get_health_returns_status_failed_on_error(monkeypatch):
    def _factory(*args: Any, **kwargs: Any) -> _FakeAsyncClient:
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(httpx, "AsyncClient", _factory)
    client = GitHubAutomationHttpClient(base_url="http://nowhere:1")
    body = _run(client.get_health())
    assert body["status"] == "failed"
    assert "boom" in body["error"]


def test_run_demo_pr_safe_failure_when_500(monkeypatch):
    _patch_httpx(monkeypatch, _FakeResponse(500, {}))
    client = GitHubAutomationHttpClient(base_url="http://github-automation:8005")
    result = _run(client.run_demo_pr({"task_id": "t3", "dry_run": True}))
    assert result["status"] == "failed"
    assert result["dry_run"] is True
    assert result["event_type"] == "github.pr.failed"


def test_read_checks_is_alias_for_get_checks(monkeypatch):
    _patch_httpx(
        monkeypatch,
        _FakeResponse(
            200,
            {
                "checks": {
                    "ref": "branchx",
                    "checks": [{"name": "build", "conclusion": "success"}],
                    "dry_run": True,
                }
            },
        ),
    )
    client = GitHubAutomationHttpClient()
    body = _run(client.read_checks("branchx", repo="owner/repo"))
    assert body["checks"]["ref"] == "branchx"
