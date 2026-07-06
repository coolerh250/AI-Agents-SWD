"""Step 59 -- sandbox GitHub client (dry_run + blocked paths, no network)."""

from __future__ import annotations

from shared.sdk.sandbox_github import SandboxGitHubClient
from shared.sdk.sandbox_github.client import SandboxGitHubClient as C


def _client() -> SandboxGitHubClient:
    return SandboxGitHubClient(actor="tester", role="operator", reason="unit test")


def _req(client, **over):
    kw = dict(
        repository_key="ai-agents-sandbox",
        project_id="pid",
        project_key="DEMO",
        work_item_id="wid",
        work_item_key="WI-0001",
        work_item_title="Add a thing",
        correlation_id="corr12345678",
    )
    kw.update(over)
    return client.request_draft_pr(**kw)


def test_client_has_no_forbidden_methods() -> None:
    forbidden = [
        a for a in dir(C) if any(t in a.lower() for t in ("merge", "ready_for_review", "workflow"))
    ]
    assert forbidden == []


def test_dry_run_planned() -> None:
    res = _req(_client(), requested_mode="dry_run")
    assert res.status == "planned"
    assert res.branch_name.startswith("sandbox/ai-agents/")
    types = [e["event_type"] for e in res.audit_events]
    assert "sandbox_github_draft_pr_requested" in types
    assert "sandbox_github_draft_pr_policy_checked" in types
    assert res.to_dict()["production_executed"] is False


def test_unknown_repo_blocked() -> None:
    res = _req(_client(), repository_key="nope")
    assert res.status == "blocked"
    assert res.reason == "repository_not_allowlisted"


def test_production_effect_blocked() -> None:
    res = _req(_client(), production_effect=True)
    assert res.status == "blocked"
    assert res.reason == "production_effect_requires_approval"
    assert res.branch_name is None


def test_live_mode_not_created_without_credential(monkeypatch) -> None:
    monkeypatch.delenv("SANDBOX_GITHUB_LIVE", raising=False)
    res = _req(_client(), requested_mode="live_sandbox")
    assert res.status != "created"


def test_live_mode_commits_evidence_before_opening_pr(monkeypatch) -> None:
    # Step 65D fix: the branch must carry a commit (evidence file) before the PR is
    # opened, otherwise GitHub rejects the PR ("no commits between base and head").
    monkeypatch.setenv("SANDBOX_GITHUB_LIVE", "true")
    monkeypatch.setenv("SANDBOX_GITHUB_TOKEN", "x" * 20)
    calls: list[tuple[str, str]] = []

    def fake_gh(self, method: str, path: str, body: dict | None = None) -> dict:
        calls.append((method, path))
        if method == "GET" and "git/ref/heads/" in path:
            return {"object": {"sha": "basesha0000"}}
        if method == "POST" and path.endswith("/pulls"):
            return {"number": 42, "html_url": "https://example.invalid/pull/42"}
        return {}

    monkeypatch.setattr(C, "_gh", fake_gh)
    res = _req(_client(), requested_mode="live_sandbox")
    assert res.status == "created"
    assert res.draft_pr_number == 42
    assert res.draft_pr_url == "https://example.invalid/pull/42"
    put_idx = next(i for i, (m, p) in enumerate(calls) if m == "PUT" and "/contents/" in p)
    pr_idx = next(i for i, (m, p) in enumerate(calls) if m == "POST" and p.endswith("/pulls"))
    assert put_idx < pr_idx, "evidence commit must precede PR creation"
    types = [e["event_type"] for e in res.audit_events]
    assert "sandbox_github_draft_evidence_committed" in types
    assert "sandbox_github_draft_pr_created" in types
