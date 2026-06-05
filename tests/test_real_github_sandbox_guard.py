"""Stage 32 -- GitHub sandbox real-write guard unit tests."""

from __future__ import annotations

from shared.sdk.real_integration import evaluate_real_github_sandbox_request
from shared.sdk.real_integration.github import PRODUCTION_REPO


def _good_env(repo: str = "owner/sandbox") -> dict[str, str]:
    return {
        "GITHUB_TOKEN": "fake",
        "GITHUB_TEST_REPO": repo,
        "RUN_REAL_GITHUB_TEST": "true",
    }


def test_valid_request_allowed():
    res = evaluate_real_github_sandbox_request(
        repo="owner/sandbox",
        branch_name="ai-agents-test/x",
        title="[AI-Agents-SWD Test] x",
        file_path="docs/github-real-test/a.md",
        env=_good_env(),
    )
    assert res.allowed is True


def test_missing_token_blocked():
    env = _good_env()
    env.pop("GITHUB_TOKEN")
    res = evaluate_real_github_sandbox_request(repo="owner/sandbox", env=env)
    assert res.allowed is False
    assert res.reason == "missing_github_token"


def test_opt_in_not_true_blocked():
    env = _good_env()
    env["RUN_REAL_GITHUB_TEST"] = "false"
    res = evaluate_real_github_sandbox_request(repo="owner/sandbox", env=env)
    assert res.allowed is False
    assert res.reason == "run_real_github_test_not_true"


def test_missing_test_repo_blocked():
    env = _good_env()
    env.pop("GITHUB_TEST_REPO")
    res = evaluate_real_github_sandbox_request(repo="owner/sandbox", env=env)
    assert res.allowed is False
    assert res.reason == "missing_github_test_repo"


def test_repo_mismatch_blocked():
    res = evaluate_real_github_sandbox_request(repo="someone/else", env=_good_env("owner/sandbox"))
    assert res.allowed is False
    assert res.reason == "repo_mismatch"


def test_production_repo_blocked_even_when_pinned():
    # Operator accidentally pinned GITHUB_TEST_REPO to the production
    # repo. The guard refuses unless the test repo carries a -sandbox
    # / _sandbox suffix.
    res = evaluate_real_github_sandbox_request(repo=PRODUCTION_REPO, env=_good_env(PRODUCTION_REPO))
    assert res.allowed is False
    assert res.reason == "production_repo_blocked"


def test_forbidden_intent_merge_blocked():
    res = evaluate_real_github_sandbox_request(
        repo="owner/sandbox",
        intent="merge",
        env=_good_env(),
    )
    assert res.allowed is False
    assert res.reason.startswith("forbidden_intent:")


def test_forbidden_intent_branch_protection_blocked():
    res = evaluate_real_github_sandbox_request(
        repo="owner/sandbox",
        intent="branch_protection",
        env=_good_env(),
    )
    assert res.allowed is False
    assert res.reason == "forbidden_intent:branch_protection"


def test_dry_run_not_false_blocked():
    res = evaluate_real_github_sandbox_request(
        repo="owner/sandbox",
        dry_run=True,
        env=_good_env(),
    )
    assert res.allowed is False
    assert res.reason == "dry_run_not_false"


def test_invalid_branch_prefix_blocked():
    res = evaluate_real_github_sandbox_request(
        repo="owner/sandbox",
        branch_name="main",
        env=_good_env(),
    )
    assert res.allowed is False
    assert res.reason == "invalid_branch_prefix"


def test_invalid_title_prefix_blocked():
    res = evaluate_real_github_sandbox_request(
        repo="owner/sandbox",
        title="plain title",
        env=_good_env(),
    )
    assert res.allowed is False
    assert res.reason == "invalid_title_prefix"


def test_file_under_dot_github_blocked():
    res = evaluate_real_github_sandbox_request(
        repo="owner/sandbox",
        file_path=".github/workflows/evil.yml",
        env=_good_env(),
    )
    assert res.allowed is False
    assert res.reason == "forbidden_repo_path"


def test_file_under_infra_blocked():
    res = evaluate_real_github_sandbox_request(
        repo="owner/sandbox",
        file_path="infra/kubernetes/evil.yaml",
        env=_good_env(),
    )
    assert res.allowed is False
    assert res.reason == "forbidden_repo_path"


def test_file_outside_allowed_prefix_blocked():
    res = evaluate_real_github_sandbox_request(
        repo="owner/sandbox",
        file_path="random/elsewhere.md",
        env=_good_env(),
    )
    assert res.allowed is False
    assert res.reason == "invalid_file_path"


def test_safe_dict_no_token_leak():
    res = evaluate_real_github_sandbox_request(repo="owner/sandbox", env=_good_env())
    assert "fake" not in repr(res.to_safe_dict())
