"""Static checks for the PR body template the github-automation service builds.

Every demo PR must include Summary / Changed Files / Risk Assessment /
Test Result / Rollback Plan so reviewers can act on it without chasing
context. The check enforces both section order and content.
"""

from __future__ import annotations


def test_build_pr_body_includes_all_required_sections(github_automation_module):
    DemoPRRequest = github_automation_module.DemoPRRequest
    build_pr_body = github_automation_module.build_pr_body
    req = DemoPRRequest(
        task_id="t1",
        body_summary="this is the summary",
        risk_assessment="this is the risk",
        test_result="this is the test result",
        rollback_plan="this is the rollback plan",
    )
    body = build_pr_body(req, ["a.md", "b.md"])
    for section in (
        "## Summary",
        "## Changed Files",
        "## Risk Assessment",
        "## Test Result",
        "## Rollback Plan",
    ):
        assert section in body, f"section {section!r} missing"
    assert "this is the summary" in body
    assert "this is the risk" in body
    assert "this is the test result" in body
    assert "this is the rollback plan" in body
    assert "a.md" in body
    assert "b.md" in body


def test_build_pr_body_section_order(github_automation_module):
    DemoPRRequest = github_automation_module.DemoPRRequest
    build_pr_body = github_automation_module.build_pr_body
    req = DemoPRRequest(task_id="t1")
    body = build_pr_body(req, ["x.md"])
    order = (
        "## Summary",
        "## Changed Files",
        "## Risk Assessment",
        "## Test Result",
        "## Rollback Plan",
    )
    indices = [body.index(s) for s in order]
    assert indices == sorted(indices), "PR body sections out of order"


def test_build_pr_body_empty_changed_files_does_not_crash(github_automation_module):
    DemoPRRequest = github_automation_module.DemoPRRequest
    build_pr_body = github_automation_module.build_pr_body
    body = build_pr_body(DemoPRRequest(task_id="t1"), [])
    assert "## Changed Files" in body
    assert "(none)" in body
