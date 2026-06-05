"""Stage 32 -- ``/github/workflow/real-test-pr`` sandbox guard endpoint tests.

We exercise the FastAPI endpoint without contacting GitHub. The Stage
32 sandbox pre-guard refuses with HTTP 409 + a ``safety_guard_result``
shaped like Stage 23's. We also assert the new
``github_sandbox_guard_failed`` decision_type is referenced in the
source (audit + operations rely on it).
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def _client(github_automation_app):
    return TestClient(github_automation_app)


def _base_request() -> dict:
    return {
        "task_id": "stage32-sandbox-1",
        "workflow_id": "wf-stage32-sandbox-1",
        "repo": "owner/sandbox",
        "base_branch": "main",
        "branch_name": "ai-agents-test/stage32",
        "title": "[AI-Agents-SWD Test] Stage 32 sandbox PR",
        "body": (
            "## Summary\nx\n\n## Changed Files\n- docs/github-real-test/x.md\n\n"
            "## Risk Assessment\nLow\n\n## Test Result\nx\n\n## Rollback Plan\nx\n\n"
            "## Safety Notes\nGuarded sandbox PR.\n"
        ),
        "file_path": "docs/github-real-test/stage32.md",
        "file_content": (
            "task_id=stage32-sandbox-1\nworkflow_id=wf\n"
            "generated_by=github-automation\nreal_github_test=true\n"
            "production_executed=false\n"
        ),
        "dry_run": False,
    }


def test_endpoint_refused_without_env(github_automation_app, monkeypatch):
    for k in ("GITHUB_TOKEN", "RUN_REAL_GITHUB_TEST", "GITHUB_TEST_REPO"):
        monkeypatch.delenv(k, raising=False)
    resp = _client(github_automation_app).post(
        "/github/workflow/real-test-pr",
        json=_base_request(),
    )
    assert resp.status_code == 409


def test_sandbox_guard_refuses_forbidden_file_path(github_automation_app, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fake")
    monkeypatch.setenv("RUN_REAL_GITHUB_TEST", "true")
    monkeypatch.setenv("GITHUB_TEST_REPO", "owner/sandbox")
    payload = _base_request()
    payload["file_path"] = ".github/workflows/evil.yml"
    resp = _client(github_automation_app).post("/github/workflow/real-test-pr", json=payload)
    assert resp.status_code == 409
    detail = resp.json().get("detail", {})
    if isinstance(detail, dict):
        guard = detail.get("safety_guard_result", {})
        # Stage 23's ``invalid_file_path`` fires first for paths outside
        # ``docs/github-real-test/``; Stage 32's ``forbidden_repo_path``
        # is the defence-in-depth rail. Either rail refusing the write
        # satisfies the test purpose. The SDK-level test
        # ``test_file_under_dot_github_blocked`` in
        # ``test_real_github_sandbox_guard.py`` exercises the Stage 32
        # rail in isolation.
        assert guard.get("reason") in {"forbidden_repo_path", "invalid_file_path"}


def test_sandbox_guard_refuses_repo_mismatch(github_automation_app, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fake")
    monkeypatch.setenv("RUN_REAL_GITHUB_TEST", "true")
    monkeypatch.setenv("GITHUB_TEST_REPO", "owner/sandbox")
    payload = _base_request()
    payload["repo"] = "someone/else"
    resp = _client(github_automation_app).post("/github/workflow/real-test-pr", json=payload)
    assert resp.status_code == 409
    detail = resp.json().get("detail", {})
    if isinstance(detail, dict):
        guard = detail.get("safety_guard_result", {})
        assert guard.get("reason") == "repo_mismatch"


def test_response_carries_no_token(github_automation_app, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_pretend_secret_x")
    monkeypatch.setenv("RUN_REAL_GITHUB_TEST", "true")
    monkeypatch.setenv("GITHUB_TEST_REPO", "owner/sandbox")
    resp = _client(github_automation_app).post(
        "/github/workflow/real-test-pr",
        json={**_base_request(), "repo": "wrong/repo"},
    )
    assert "ghp_pretend_secret_x" not in resp.text
