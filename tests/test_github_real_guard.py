"""Stage 23 safety guard unit tests.

Every Stage 23 pre-condition is exercised in isolation. No real GitHub
API call is made; ``evaluate_real_test_request`` is pure.
"""

from __future__ import annotations

import sys

import pytest


@pytest.fixture(scope="module")
def guard_module():
    # conftest preloads real_guard.py under the canonical "real_guard"
    # module name so apps/github-automation/src/main.py can ``from
    # real_guard import``. Reuse that single instance here to avoid the
    # Python 3.14 dataclass re-registration race.
    return sys.modules["real_guard"]


def _valid_kwargs(**overrides):
    base = dict(
        repo="coolerh250/AI-Agents-SWD",
        base_branch="main",
        branch_name="ai-agents-test/sample-task",
        title="[AI-Agents-SWD Test] Sample real validation",
        body=(
            "## Summary\nx\n\n## Changed Files\n- docs/github-real-test/sample.md\n\n"
            "## Risk Assessment\nLow\n\n## Test Result\nx\n\n## Rollback Plan\nx\n\n"
            "## Safety Notes\nGuarded sandbox PR.\n"
        ),
        file_path="docs/github-real-test/sample.md",
        file_content=(
            "task_id=sample-task\nworkflow_id=wf\n"
            "generated_by=github-automation\nreal_github_test=true\n"
            "production_executed=false\n"
        ),
        dry_run=False,
        env={
            "GITHUB_TOKEN": "fake-token-do-not-use",
            "RUN_REAL_GITHUB_TEST": "true",
            "GITHUB_TEST_REPO": "coolerh250/AI-Agents-SWD",
        },
    )
    base.update(overrides)
    return base


def test_valid_request_is_allowed(guard_module):
    result = guard_module.evaluate_real_test_request(**_valid_kwargs())
    assert result.allowed is True
    assert result.reason == ""
    # safe-dict must never contain the token under any field
    safe = result.to_safe_dict()
    assert "token" not in repr(safe).lower()


def test_missing_token_blocked(guard_module):
    result = guard_module.evaluate_real_test_request(
        **_valid_kwargs(env={"RUN_REAL_GITHUB_TEST": "true", "GITHUB_TEST_REPO": "x/y"})
    )
    assert result.allowed is False
    assert result.reason == "missing_github_token"


def test_run_real_github_test_not_true_blocked(guard_module):
    result = guard_module.evaluate_real_test_request(
        **_valid_kwargs(env={"GITHUB_TOKEN": "t", "GITHUB_TEST_REPO": "x/y"})
    )
    assert result.allowed is False
    assert result.reason == "run_real_github_test_not_true"


def test_missing_github_test_repo_blocked(guard_module):
    result = guard_module.evaluate_real_test_request(
        **_valid_kwargs(env={"GITHUB_TOKEN": "t", "RUN_REAL_GITHUB_TEST": "true"})
    )
    assert result.allowed is False
    assert result.reason == "missing_github_test_repo"


def test_repo_mismatch_blocked(guard_module):
    result = guard_module.evaluate_real_test_request(**_valid_kwargs(repo="someone-else/repo"))
    assert result.allowed is False
    assert result.reason == "repo_mismatch"


def test_invalid_branch_prefix_blocked(guard_module):
    result = guard_module.evaluate_real_test_request(**_valid_kwargs(branch_name="feature/x"))
    assert result.allowed is False
    assert result.reason == "invalid_branch_prefix"


def test_invalid_title_prefix_blocked(guard_module):
    result = guard_module.evaluate_real_test_request(**_valid_kwargs(title="[release] x"))
    assert result.allowed is False
    assert result.reason == "invalid_title_prefix"


@pytest.mark.parametrize("base", ["production", "prod", "release/2026.01"])
def test_production_base_branch_blocked(guard_module, base):
    result = guard_module.evaluate_real_test_request(**_valid_kwargs(base_branch=base))
    assert result.allowed is False
    assert result.reason == "production_base_branch"


@pytest.mark.parametrize("dr", [True, None, "false", 0])
def test_dry_run_not_explicit_false_blocked(guard_module, dr):
    result = guard_module.evaluate_real_test_request(**_valid_kwargs(dry_run=dr))
    assert result.allowed is False
    assert result.reason == "dry_run_not_false"


def test_invalid_file_path_blocked(guard_module):
    result = guard_module.evaluate_real_test_request(**_valid_kwargs(file_path="src/main.py"))
    assert result.allowed is False
    assert result.reason == "invalid_file_path"


def test_missing_file_markers_blocked(guard_module):
    result = guard_module.evaluate_real_test_request(**_valid_kwargs(file_content="hello world\n"))
    assert result.allowed is False
    assert result.reason == "missing_file_markers"
    assert "production_executed=false" in result.details["missing"]


def test_missing_safety_notes_blocked(guard_module):
    body_without_safety = (
        "## Summary\nx\n\n## Changed Files\n- x.md\n\n"
        "## Risk Assessment\nLow\n\n## Test Result\nx\n\n## Rollback Plan\nx\n"
    )
    result = guard_module.evaluate_real_test_request(**_valid_kwargs(body=body_without_safety))
    assert result.allowed is False
    assert result.reason == "missing_pr_sections"
    assert "## Safety Notes" in result.details["missing"]


def test_to_safe_dict_carries_no_token_field(guard_module):
    """No matter the failure mode, the safe-dict never carries token-shaped fields."""
    result = guard_module.evaluate_real_test_request(
        **_valid_kwargs(env={"GITHUB_TOKEN": "secret-please-never-leak"})
    )
    safe = result.to_safe_dict()
    assert "secret-please-never-leak" not in repr(safe)
