"""Step 59 -- sandbox GitHub policy loading + mode resolution."""

from __future__ import annotations

from shared.sdk.sandbox_github import policy
from shared.sdk.sandbox_github.models import MODE_DRY_RUN, MODE_LIVE_SANDBOX


def test_policy_defaults_and_toggles() -> None:
    p = policy.load_policy()
    assert p["enabled"] is True
    assert p["productionReady"] is False
    assert p["defaultMode"] == "dry_run"
    for key in (
        "allowMerge",
        "allowReadyForReview",
        "allowNonSandboxRepo",
        "allowProductionBranch",
        "allowWorkflowDispatch",
        "allowIssueWrite",
        "allowReleaseWrite",
        "allowDeploymentWrite",
    ):
        assert p[key] is False


def test_resolve_mode_dry_run_default() -> None:
    assert policy.resolve_mode(None) == (MODE_DRY_RUN, None)
    assert policy.resolve_mode("dry_run") == (MODE_DRY_RUN, None)


def test_resolve_mode_invalid() -> None:
    mode, reason = policy.resolve_mode("merge_now")
    assert mode == MODE_DRY_RUN
    assert reason and reason.startswith("invalid_mode")


def test_live_sandbox_blocked_without_enable(monkeypatch) -> None:
    monkeypatch.delenv("SANDBOX_GITHUB_LIVE", raising=False)
    mode, reason = policy.resolve_mode("live_sandbox")
    assert mode == MODE_LIVE_SANDBOX
    assert reason == "live_sandbox_not_enabled"
    assert policy.live_mode_effective() is False


def test_live_sandbox_blocked_without_credential(monkeypatch) -> None:
    monkeypatch.setenv("SANDBOX_GITHUB_LIVE", "true")
    monkeypatch.delenv("SANDBOX_GITHUB_TOKEN", raising=False)
    mode, reason = policy.resolve_mode("live_sandbox")
    assert reason == "live_sandbox_no_credential"
    assert policy.live_mode_effective() is False
