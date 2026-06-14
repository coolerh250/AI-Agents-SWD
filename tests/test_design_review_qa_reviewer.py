"""Stage 46 -- QA reviewer tests."""

from __future__ import annotations

from design_review_fakes import build_fastapi_todo_context

from shared.sdk.design_review.models import ReviewContext
from shared.sdk.design_review.qa_reviewer import review_qa


def test_fastapi_todo_qa_clean() -> None:
    # QA work items + integration_test criteria + README -> clean
    findings = review_qa(build_fastapi_todo_context())
    assert findings == []


def test_no_qa_work_item_flags_high() -> None:
    ctx = ReviewContext(
        project_id="p",
        work_items=[{"work_type": "backend", "id": "1"}],
        acceptance_criteria=[{"description": "x", "verification_method": "manual_review"}],
    )
    findings = review_qa(ctx)
    assert any(f.finding_key == "QA-NO-WORK-ITEM" and f.severity == "high" for f in findings)


def test_no_test_criteria_flagged() -> None:
    ctx = ReviewContext(
        project_id="p",
        work_items=[{"work_type": "qa", "id": "1"}],
        acceptance_criteria=[
            {"description": "manual check", "verification_method": "manual_review"}
        ],
    )
    findings = review_qa(ctx)
    assert any(f.finding_key == "QA-NO-TESTS" for f in findings)
