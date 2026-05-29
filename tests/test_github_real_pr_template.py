"""Stage 23 PR body template static checks.

The real-test PR template is supplied by the caller. The guard rejects
any body that omits the six required sections (including
``## Safety Notes``). This test pins the section set so a future
refactor can't accidentally relax the contract.
"""

from __future__ import annotations

import sys

import pytest


@pytest.fixture(scope="module")
def guard_module():
    return sys.modules["real_guard"]


def test_required_sections_include_safety_notes(guard_module):
    assert "## Safety Notes" in guard_module.REQUIRED_PR_SECTIONS


def test_required_sections_set(guard_module):
    expected = (
        "## Summary",
        "## Changed Files",
        "## Risk Assessment",
        "## Test Result",
        "## Rollback Plan",
        "## Safety Notes",
    )
    assert tuple(guard_module.REQUIRED_PR_SECTIONS) == expected


def test_required_file_markers_pin_production_executed_false(guard_module):
    assert "production_executed=false" in guard_module.REQUIRED_FILE_MARKERS
    assert "real_github_test=true" in guard_module.REQUIRED_FILE_MARKERS
    assert "generated_by=github-automation" in guard_module.REQUIRED_FILE_MARKERS


def test_branch_prefix_pinned(guard_module):
    assert guard_module.ALLOWED_BRANCH_PREFIX == "ai-agents-test/"


def test_title_prefix_pinned(guard_module):
    assert guard_module.ALLOWED_TITLE_PREFIX == "[AI-Agents-SWD Test]"


def test_file_prefix_pinned(guard_module):
    assert guard_module.ALLOWED_FILE_PREFIX == "docs/github-real-test/"


def test_pr_template_body_template_is_callable(github_automation_module):
    """The endpoint exposes ``build_real_test_pr_body`` for callers
    that pre-render. It returns the request body verbatim — Stage 23
    deliberately does not mutate caller PR text.
    """
    build_real_test_pr_body = github_automation_module.build_real_test_pr_body
    RealTestPRRequest = github_automation_module.RealTestPRRequest
    body_text = (
        "## Summary\nx\n\n## Changed Files\n- x.md\n\n"
        "## Risk Assessment\nx\n\n## Test Result\nx\n\n## Rollback Plan\nx\n\n"
        "## Safety Notes\nx\n"
    )
    req = RealTestPRRequest(
        task_id="t",
        repo="owner/repo",
        branch_name="ai-agents-test/t",
        title="[AI-Agents-SWD Test] x",
        body=body_text,
        file_path="docs/github-real-test/x.md",
        file_content="x",
    )
    assert build_real_test_pr_body(req) == body_text
