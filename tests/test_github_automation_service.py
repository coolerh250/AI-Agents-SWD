"""Service-level tests for apps/github-automation.

All requests run with dry_run=True (the service default). No real GitHub
API call is issued and no GITHUB_TOKEN is required.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health(github_automation_app):
    client = TestClient(github_automation_app)
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["service"] == "github-automation"
    assert body["status"] == "ok"
    assert "default_repo" in body
    assert body["default_dry_run"] is True


def test_create_issue_dry_run(github_automation_app):
    client = TestClient(github_automation_app)
    res = client.post(
        "/github/issue",
        json={
            "repo": "owner/repo",
            "title": "smoke",
            "body": "smoke body",
            "task_id": "test-1",
            "dry_run": True,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["dry_run"] is True
    assert body["issue"]["title"] == "smoke"
    assert body["issue"]["dry_run"] is True
    assert "issues" in body["issue"]["url"]


def test_create_branch_dry_run(github_automation_app):
    client = TestClient(github_automation_app)
    res = client.post(
        "/github/branch",
        json={"repo": "owner/repo", "name": "feature/smoke", "base_branch": "main"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["dry_run"] is True
    assert body["branch"]["name"] == "feature/smoke"
    assert len(body["branch"]["sha"]) == 40


def test_create_or_update_file_dry_run(github_automation_app):
    client = TestClient(github_automation_app)
    res = client.post(
        "/github/file",
        json={
            "repo": "owner/repo",
            "path": "docs/x.md",
            "content": "hello",
            "message": "test",
            "branch": "feature/smoke",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["dry_run"] is True
    assert body["file"]["path"] == "docs/x.md"
    assert body["file"]["content_preview"].startswith("hello")


def test_create_pull_request_dry_run(github_automation_app):
    client = TestClient(github_automation_app)
    res = client.post(
        "/github/pull-request",
        json={
            "repo": "owner/repo",
            "title": "[AI-Agents-SWD Test] smoke",
            "body": "body",
            "head_branch": "feature/smoke",
            "base_branch": "main",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["dry_run"] is True
    assert body["pull_request"]["state"] == "open"
    assert "pull" in body["pull_request"]["url"]


def test_get_pull_request_dry_run(github_automation_app):
    client = TestClient(github_automation_app)
    res = client.get("/github/pull-request/42?dry_run=true&repo=owner/repo")
    assert res.status_code == 200
    body = res.json()
    assert body["pull_request"]["number"] == 42
    assert body["pull_request"]["dry_run"] is True


def test_get_checks_dry_run(github_automation_app):
    client = TestClient(github_automation_app)
    res = client.get("/github/checks?ref=feature/smoke&dry_run=true&repo=owner/repo")
    assert res.status_code == 200
    body = res.json()
    assert body["checks"]["count"] >= 1
    assert body["checks"]["dry_run"] is True


def test_metrics_endpoint_exposes_github_counters(github_automation_app):
    client = TestClient(github_automation_app)
    # Trigger at least one increment.
    client.post(
        "/github/issue",
        json={"repo": "owner/repo", "title": "metrics warm-up"},
    )
    res = client.get("/metrics")
    body = res.text
    for counter in (
        "github_issue_created_total",
        "github_branch_created_total",
        "github_pr_created_total",
        "github_checks_read_total",
        "github_automation_failures_total",
    ):
        assert counter in body, f"metric {counter!r} missing from /metrics"
