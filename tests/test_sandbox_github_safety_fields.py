"""Step 59 -- sandbox GitHub safety fields posture."""

from __future__ import annotations

from shared.sdk.sandbox_github import sandbox_github_safety_fields


def test_safety_fields_posture() -> None:
    f = sandbox_github_safety_fields()
    assert f["sandbox_github_draft_pr_enabled"] is True
    assert f["sandbox_github_draft_pr_default_mode"] == "dry_run"
    assert f["sandbox_github_repository_allowlist_enabled"] is True
    for key in (
        "sandbox_github_arbitrary_repo_allowed",
        "sandbox_github_merge_enabled",
        "sandbox_github_ready_for_review_enabled",
        "sandbox_github_workflow_dispatch_enabled",
        "sandbox_github_issue_write_enabled",
        "sandbox_github_release_write_enabled",
        "sandbox_github_deployment_write_enabled",
        "sandbox_github_token_exposed",
        "sandbox_github_production_branch_allowed",
        "sandbox_github_non_sandbox_repo_write_performed",
        "sandbox_github_production_ready",
    ):
        assert f[key] is False, key


def test_live_mode_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("SANDBOX_GITHUB_LIVE", raising=False)
    monkeypatch.delenv("SANDBOX_GITHUB_TOKEN", raising=False)
    f = sandbox_github_safety_fields()
    assert f["sandbox_github_draft_pr_live_mode_enabled"] is False
    assert f["sandbox_github_draft_pr_created_count"] == 0


def test_created_count_passthrough() -> None:
    f = sandbox_github_safety_fields(draft_pr_created_count=3)
    assert f["sandbox_github_draft_pr_created_count"] == 3
