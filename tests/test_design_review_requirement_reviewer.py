"""Stage 46 -- requirement reviewer tests."""

from __future__ import annotations

from design_review_fakes import build_fastapi_todo_context

from shared.sdk.design_review.models import ReviewContext
from shared.sdk.design_review.requirement_reviewer import review_requirements


def test_fastapi_todo_requirements_clean() -> None:
    findings = review_requirements(build_fastapi_todo_context())
    # scope/non_scope/stories present and CRUD/test/doc covered -> no findings
    assert findings == []


def test_missing_scope_flags_high() -> None:
    ctx = ReviewContext(project_id="p", brief={"non_scope": ["x"]}, user_stories=[{"k": 1}])
    findings = review_requirements(ctx)
    assert any(f.finding_key == "REQ-SCOPE" and f.severity == "high" for f in findings)


def test_clarification_flagged() -> None:
    ctx = ReviewContext(
        project_id="p",
        brief={"scope": ["x"], "non_scope": ["y"], "metadata": {"requires_clarification": True}},
        user_stories=[{"k": 1}],
        acceptance_criteria=[{"description": "create list get update delete pytest readme"}],
    )
    findings = review_requirements(ctx)
    assert any(f.finding_key == "REQ-CLARIFY" for f in findings)
