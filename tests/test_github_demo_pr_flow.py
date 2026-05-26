"""End-to-end (in-process) test for the github-automation /demo-pr flow.

We assert the dry-run aggregate response covers every step (issue,
branch, file, PR, checks) and that the dry_run flag is faithfully
propagated. We do NOT exercise the real GitHub API.

The notification + audit side effects are best-effort and gated on
Redis / audit-service being reachable. We assert the response shape
and rely on tests/test_github_tracing_metrics.py for the
notification + audit smoke against a real cluster (skip when Redis
is unreachable).
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def _new_task() -> str:
    return f"demo-pr-{uuid.uuid4().hex[:8]}"


def test_demo_pr_dry_run_returns_full_envelope(github_automation_app):
    client = TestClient(github_automation_app)
    task_id = _new_task()
    res = client.post(
        "/github/workflow/demo-pr",
        json={
            "task_id": task_id,
            "workflow_id": "wf-" + task_id,
            "repo": "owner/repo",
            "base_branch": "main",
            "branch_name": f"ai-agents-swd/demo-{task_id}",
            "title": "[AI-Agents-SWD Test] demo PR",
            "body_summary": "demo PR body",
            "file_path": "docs/x.md",
            "file_content": "hello",
            "dry_run": True,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["dry_run"] is True
    assert body["task_id"] == task_id
    assert body["base_branch"] == "main"

    # Each step must be present and carry dry_run=True.
    for step in ("issue", "branch", "file", "pull_request", "checks"):
        assert step in body, f"missing step {step!r} in demo-pr response"
        assert body[step]["dry_run"] is True

    # Notification event_type is the dry-run variant.
    assert body["event_type"] == "github.pr.dry_run"

    # URLs are GitHub URLs of the requested repo.
    assert "owner/repo" in body["issue"]["url"]
    assert "owner/repo" in body["pull_request"]["url"]


def test_demo_pr_dry_run_defaults_when_dry_run_omitted(github_automation_app):
    """Omitting ``dry_run`` from the body must fall back to the default
    (which is True for the service)."""
    client = TestClient(github_automation_app)
    task_id = _new_task()
    res = client.post(
        "/github/workflow/demo-pr",
        json={"task_id": task_id},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["dry_run"] is True
    assert body["event_type"] == "github.pr.dry_run"


def test_demo_pr_pr_body_contains_required_sections(github_automation_app):
    client = TestClient(github_automation_app)
    task_id = _new_task()
    res = client.post(
        "/github/workflow/demo-pr",
        json={
            "task_id": task_id,
            "body_summary": "Summary text",
            "risk_assessment": "Risk text",
            "test_result": "Test result text",
            "rollback_plan": "Rollback text",
            "file_path": "docs/x.md",
        },
    )
    assert res.status_code == 200
    pr_body = res.json()["pull_request"]["body"]
    for section in (
        "## Summary",
        "## Changed Files",
        "## Risk Assessment",
        "## Test Result",
        "## Rollback Plan",
    ):
        assert section in pr_body, f"PR body missing section {section!r}"
    # File path must be listed under Changed Files.
    assert "docs/x.md" in pr_body
