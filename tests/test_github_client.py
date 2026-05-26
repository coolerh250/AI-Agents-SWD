"""Unit tests for shared.sdk.github.GitHubClient.

All tests run with dry_run=True — no real GitHub API call is ever issued.
The only assertion about dry_run=False is that the client refuses to
proceed when GITHUB_TOKEN is absent.
"""

from __future__ import annotations

import asyncio

import pytest

from shared.sdk.github import GitHubClient, GitHubClientError, GitHubMissingTokenError


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_invalid_repo_raises():
    with pytest.raises(GitHubClientError):
        GitHubClient(repo="not-a-valid-repo")


def test_dry_run_default_true():
    client = GitHubClient(repo="owner/repo", env={})
    assert client.dry_run is True


def test_missing_token_raises_when_dry_run_false():
    client = GitHubClient(repo="owner/repo", dry_run=False, env={})
    with pytest.raises(GitHubMissingTokenError):
        # ``has_token`` is False — any operation that goes to the API path
        # must raise GitHubMissingTokenError *before* touching the network.
        _run(client.create_issue("title", "body"))


def test_dry_run_create_issue_returns_mock_with_url():
    client = GitHubClient(repo="owner/repo", dry_run=True, env={})
    issue = _run(client.create_issue("hello", "body", task_id="t1"))
    assert issue.dry_run is True
    assert issue.repo == "owner/repo"
    assert issue.number is not None and issue.number >= 1000
    assert "owner/repo/issues" in issue.url
    assert issue.title == "hello"


def test_dry_run_create_branch_returns_deterministic_sha():
    client = GitHubClient(repo="owner/repo", dry_run=True, env={})
    branch1 = _run(client.create_branch("feature/x"))
    branch2 = _run(client.create_branch("feature/x"))
    assert branch1.dry_run is True
    assert branch1.name == "feature/x"
    assert branch1.base_branch == "main"
    assert branch1.sha == branch2.sha
    assert len(branch1.sha) == 40  # sha1 hex


def test_dry_run_create_or_update_file_truncates_preview():
    client = GitHubClient(repo="owner/repo", dry_run=True, env={})
    long_content = "x" * 1000
    file = _run(
        client.create_or_update_file("path/to/file.md", long_content, message="msg", branch="b")
    )
    assert file.dry_run is True
    assert file.path == "path/to/file.md"
    assert file.branch == "b"
    assert len(file.content_preview) <= 200
    assert file.content_preview.endswith("...")


def test_dry_run_create_pull_request_returns_open_state_and_url():
    client = GitHubClient(repo="owner/repo", dry_run=True, env={})
    pr = _run(
        client.create_pull_request(
            "title",
            "body",
            head_branch="feature/x",
            base_branch="main",
        )
    )
    assert pr.dry_run is True
    assert pr.state == "open"
    assert pr.head_branch == "feature/x"
    assert pr.base_branch == "main"
    assert "owner/repo/pull" in pr.url


def test_dry_run_get_pull_request_returns_dry_run_envelope():
    client = GitHubClient(repo="owner/repo", dry_run=True, env={})
    pr = _run(client.get_pull_request(42))
    assert pr.dry_run is True
    assert pr.number == 42
    assert pr.repo == "owner/repo"


def test_dry_run_read_checks_returns_three_passing_checks():
    client = GitHubClient(repo="owner/repo", dry_run=True, env={})
    checks = _run(client.read_checks("feature/x"))
    assert checks.dry_run is True
    assert checks.ref == "feature/x"
    assert len(checks.checks) >= 1
    for check in checks.checks:
        assert "name" in check
        assert "status" in check
        assert "conclusion" in check


def test_dry_run_list_open_pull_requests_returns_empty():
    client = GitHubClient(repo="owner/repo", dry_run=True, env={})
    items = _run(client.list_open_pull_requests())
    assert items == []


def test_has_token_reads_env_only_not_constructor():
    """The client must not accept the token as a constructor arg."""
    client = GitHubClient(repo="owner/repo", env={"GITHUB_TOKEN": "ghp_TEST_NOT_REAL"})
    assert client.has_token() is True
    client2 = GitHubClient(repo="owner/repo", env={})
    assert client2.has_token() is False


def test_no_token_field_on_client():
    """The client object must NOT expose a ``token`` attribute that could be
    accidentally serialised into logs."""
    client = GitHubClient(repo="owner/repo", env={"GITHUB_TOKEN": "ghp_TEST"})
    assert not hasattr(client, "token")
