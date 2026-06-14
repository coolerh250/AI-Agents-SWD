"""Stage 46 -- delivery reviewer tests."""

from __future__ import annotations

from design_review_fakes import build_fastapi_todo_context

from shared.sdk.design_review.delivery_reviewer import review_delivery
from shared.sdk.design_review.models import ReviewContext


def test_fastapi_todo_delivery_path_exists() -> None:
    findings = review_delivery(build_fastapi_todo_context())
    # release work item (DEL-001) + README present -> only the accepted readiness note
    assert not any(f.finding_key == "DEL-NO-SUMMARY" for f in findings)
    pending = [f for f in findings if f.finding_key == "DEL-READINESS-PENDING"]
    assert pending and pending[0].status == "accepted"


def test_no_delivery_item_flagged() -> None:
    ctx = ReviewContext(
        project_id="p",
        work_items=[{"work_type": "backend", "title": "impl", "id": "1"}],
        acceptance_criteria=[{"description": "readme"}],
    )
    findings = review_delivery(ctx)
    assert any(f.finding_key == "DEL-NO-SUMMARY" for f in findings)
