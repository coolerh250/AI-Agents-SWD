"""Stage 23 endpoint tests for POST /github/workflow/real-test-pr.

Every test runs against the FastAPI app in-process. No real GitHub API
call is made — the controlled-real path is exercised only via a stubbed
``GitHubClient``. The token never appears in any response.
"""

from __future__ import annotations

import os
from typing import Any

import pytest
from fastapi.testclient import TestClient

VALID_BODY = {
    "task_id": "real-task-1",
    "workflow_id": "wf-real-task-1",
    # Stage 32: pinned sandbox repo (production repo is blocked by the
    # new Stage 32 sandbox guard). The original tests pinned the
    # canonical production repo here; that's intentionally refused now.
    "repo": "coolerh250/AI-Agents-SWD-sandbox",
    "base_branch": "main",
    "branch_name": "ai-agents-test/real-task-1",
    "title": "[AI-Agents-SWD Test] valid real PR",
    "body": (
        "## Summary\nx\n\n## Changed Files\n- docs/github-real-test/real-task-1.md\n\n"
        "## Risk Assessment\nLow\n\n## Test Result\nx\n\n## Rollback Plan\nx\n\n"
        "## Safety Notes\nGuard verifies repo + branch + title prefix.\n"
    ),
    "file_path": "docs/github-real-test/real-task-1.md",
    "file_content": (
        "task_id=real-task-1\nworkflow_id=wf-real-task-1\n"
        "generated_by=github-automation\nreal_github_test=true\n"
        "production_executed=false\n"
    ),
    "dry_run": False,
}


def _post(client: TestClient, **overrides: Any):
    body = dict(VALID_BODY)
    body.update(overrides)
    return client.post("/github/workflow/real-test-pr", json=body)


def test_blocked_without_env(github_automation_app, monkeypatch):
    for var in ("GITHUB_TOKEN", "RUN_REAL_GITHUB_TEST", "GITHUB_TEST_REPO"):
        monkeypatch.delenv(var, raising=False)
    client = TestClient(github_automation_app)
    res = _post(client)
    assert res.status_code == 409
    detail = res.json()["detail"]
    assert detail["safety_guard_result"]["allowed"] is False
    assert detail["safety_guard_result"]["reason"] == "missing_github_token"


def test_blocked_when_run_real_github_test_false(github_automation_app, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "x")
    monkeypatch.setenv("RUN_REAL_GITHUB_TEST", "false")
    monkeypatch.delenv("GITHUB_TEST_REPO", raising=False)
    client = TestClient(github_automation_app)
    res = _post(client)
    assert res.status_code == 409
    assert res.json()["detail"]["safety_guard_result"]["reason"] == "run_real_github_test_not_true"


def test_blocked_when_test_repo_missing(github_automation_app, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "x")
    monkeypatch.setenv("RUN_REAL_GITHUB_TEST", "true")
    monkeypatch.delenv("GITHUB_TEST_REPO", raising=False)
    client = TestClient(github_automation_app)
    res = _post(client)
    assert res.status_code == 409
    assert res.json()["detail"]["safety_guard_result"]["reason"] == "missing_github_test_repo"


def test_blocked_on_repo_mismatch(github_automation_app, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "x")
    monkeypatch.setenv("RUN_REAL_GITHUB_TEST", "true")
    monkeypatch.setenv("GITHUB_TEST_REPO", "expected/repo")
    client = TestClient(github_automation_app)
    res = _post(client, repo="someone-else/AI-Agents-SWD")
    assert res.status_code == 409
    assert res.json()["detail"]["safety_guard_result"]["reason"] == "repo_mismatch"


def test_blocked_on_invalid_branch_prefix(github_automation_app, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "x")
    monkeypatch.setenv("RUN_REAL_GITHUB_TEST", "true")
    monkeypatch.setenv("GITHUB_TEST_REPO", VALID_BODY["repo"])
    client = TestClient(github_automation_app)
    res = _post(client, branch_name="feature/x")
    assert res.status_code == 409
    assert res.json()["detail"]["safety_guard_result"]["reason"] == "invalid_branch_prefix"


def test_blocked_on_invalid_title_prefix(github_automation_app, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "x")
    monkeypatch.setenv("RUN_REAL_GITHUB_TEST", "true")
    monkeypatch.setenv("GITHUB_TEST_REPO", VALID_BODY["repo"])
    client = TestClient(github_automation_app)
    res = _post(client, title="bad title")
    assert res.status_code == 409
    assert res.json()["detail"]["safety_guard_result"]["reason"] == "invalid_title_prefix"


def test_blocked_on_production_base_branch(github_automation_app, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "x")
    monkeypatch.setenv("RUN_REAL_GITHUB_TEST", "true")
    monkeypatch.setenv("GITHUB_TEST_REPO", VALID_BODY["repo"])
    client = TestClient(github_automation_app)
    res = _post(client, base_branch="production")
    assert res.status_code == 409
    assert res.json()["detail"]["safety_guard_result"]["reason"] == "production_base_branch"


def test_blocked_when_dry_run_omitted_defaults_to_none(github_automation_app, monkeypatch):
    """``dry_run`` defaults to ``None`` on the pydantic model, which the
    guard treats as "not explicit" → blocked. The caller must opt in.
    """
    monkeypatch.setenv("GITHUB_TOKEN", "x")
    monkeypatch.setenv("RUN_REAL_GITHUB_TEST", "true")
    monkeypatch.setenv("GITHUB_TEST_REPO", VALID_BODY["repo"])
    client = TestClient(github_automation_app)
    body = dict(VALID_BODY)
    body.pop("dry_run", None)
    res = client.post("/github/workflow/real-test-pr", json=body)
    assert res.status_code == 409
    assert res.json()["detail"]["safety_guard_result"]["reason"] == "dry_run_not_false"


def test_blocked_when_file_path_out_of_scope(github_automation_app, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "x")
    monkeypatch.setenv("RUN_REAL_GITHUB_TEST", "true")
    monkeypatch.setenv("GITHUB_TEST_REPO", VALID_BODY["repo"])
    client = TestClient(github_automation_app)
    res = _post(client, file_path="src/main.py")
    assert res.status_code == 409
    assert res.json()["detail"]["safety_guard_result"]["reason"] == "invalid_file_path"


def test_response_never_contains_token(github_automation_app, monkeypatch):
    secret = "ghp_pleaseneverleakthisstring"
    monkeypatch.setenv("GITHUB_TOKEN", secret)
    monkeypatch.setenv("RUN_REAL_GITHUB_TEST", "false")
    monkeypatch.delenv("GITHUB_TEST_REPO", raising=False)
    client = TestClient(github_automation_app)
    res = _post(client)
    assert res.status_code == 409
    assert secret not in res.text


def test_dry_run_demo_pr_does_not_regress(github_automation_app, monkeypatch):
    """The Stage 17 demo endpoint must still run dry-run cleanly even
    when Stage 23 env vars are present.
    """
    monkeypatch.setenv("GITHUB_TOKEN", "x")
    monkeypatch.setenv("RUN_REAL_GITHUB_TEST", "true")
    monkeypatch.setenv("GITHUB_TEST_REPO", VALID_BODY["repo"])
    client = TestClient(github_automation_app)
    res = client.post(
        "/github/workflow/demo-pr",
        json={"task_id": "regression-1", "dry_run": True},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["dry_run"] is True
    assert body["pull_request"]["dry_run"] is True


def test_allowed_path_executes_full_flow_with_stubbed_client(
    github_automation_app, github_automation_module, monkeypatch
):
    """When every Stage 23 pre-condition holds, the endpoint runs the
    issue → branch → file → PR → checks flow. We stub GitHubClient so
    no real API call leaves the process; the token, even though present
    in the env, never appears in the response.
    """
    secret = "ghp_pleaseneverleakthisstring"
    monkeypatch.setenv("GITHUB_TOKEN", secret)
    monkeypatch.setenv("RUN_REAL_GITHUB_TEST", "true")
    monkeypatch.setenv("GITHUB_TEST_REPO", VALID_BODY["repo"])

    class _StubIssue:
        def to_dict(self):
            return {
                "repo": VALID_BODY["repo"],
                "number": 1,
                "title": VALID_BODY["title"],
                "url": f"https://github.com/{VALID_BODY['repo']}/issues/1",
                "dry_run": False,
            }

    class _StubBranch:
        def to_dict(self):
            return {
                "repo": VALID_BODY["repo"],
                "name": VALID_BODY["branch_name"],
                "sha": "x" * 40,
                "base_branch": VALID_BODY["base_branch"],
                "dry_run": False,
            }

    class _StubFile:
        def to_dict(self):
            return {
                "repo": VALID_BODY["repo"],
                "branch": VALID_BODY["branch_name"],
                "path": VALID_BODY["file_path"],
                "content_preview": "task_id",
                "sha": "y" * 40,
                "dry_run": False,
            }

    class _StubPR:
        def to_dict(self):
            return {
                "repo": VALID_BODY["repo"],
                "number": 42,
                "title": VALID_BODY["title"],
                "body": VALID_BODY["body"],
                "base_branch": VALID_BODY["base_branch"],
                "head_branch": VALID_BODY["branch_name"],
                "url": f"https://github.com/{VALID_BODY['repo']}/pull/42",
                "state": "open",
                "dry_run": False,
            }

    class _StubChecks:
        def to_dict(self):
            return {
                "repo": VALID_BODY["repo"],
                "ref": VALID_BODY["branch_name"],
                "count": 1,
                "checks": [{"name": "build", "status": "completed", "conclusion": "success"}],
                "dry_run": False,
            }

    class _StubClient:
        def __init__(self, repo: str, dry_run: bool = False, **_: Any) -> None:
            assert dry_run is False
            self.repo = repo

        async def create_issue(self, **_: Any) -> _StubIssue:
            return _StubIssue()

        async def create_branch(self, *_args: Any, **_: Any) -> _StubBranch:
            return _StubBranch()

        async def create_or_update_file(self, *_args: Any, **_: Any) -> _StubFile:
            return _StubFile()

        async def create_pull_request(self, **_: Any) -> _StubPR:
            return _StubPR()

        async def read_checks(self, *_args: Any, **_: Any) -> _StubChecks:
            return _StubChecks()

    async def _noop_audit(**_: Any) -> None:
        return None

    monkeypatch.setattr(github_automation_module, "GitHubClient", _StubClient)
    monkeypatch.setattr(github_automation_module, "_record_real_test_audit", _noop_audit)
    monkeypatch.setattr(
        github_automation_module,
        "_publish_real_test_notification",
        lambda *a, **k: _noop_audit(),
    )

    client = TestClient(github_automation_app)
    res = _post(client)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["dry_run"] is False
    assert body["real_github_test"] is True
    assert body["production_executed"] is False
    assert body["pull_request"]["number"] == 42
    assert body["issue"]["number"] == 1
    assert body["safety_guard_result"]["allowed"] is True
    # token must not leak under any field
    assert secret not in res.text


def test_health_exposes_real_test_flags(github_automation_app, monkeypatch):
    monkeypatch.setenv("RUN_REAL_GITHUB_TEST", "true")
    monkeypatch.setenv("GITHUB_TEST_REPO", "x/y")
    client = TestClient(github_automation_app)
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["real_github_test_enabled"] is True
    assert body["test_repo_configured"] is True


@pytest.fixture(autouse=True)
def _restore_env():
    """Tests above mutate env vars; reset to avoid bleed across tests."""
    snapshot = dict(os.environ)
    yield
    for key in list(os.environ.keys()):
        if key not in snapshot:
            del os.environ[key]
    os.environ.update(snapshot)
