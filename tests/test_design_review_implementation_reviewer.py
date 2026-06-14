"""Stage 46 -- implementation reviewer tests."""

from __future__ import annotations

from design_review_fakes import build_fastapi_todo_context

from shared.sdk.design_review.implementation_reviewer import review_implementation
from shared.sdk.design_review.models import ReviewContext


def test_fastapi_todo_implementation_clean() -> None:
    findings = review_implementation(build_fastapi_todo_context())
    # BE-002 maps to acceptance criteria -> no AC-coverage finding; graph valid
    assert all(f.severity != "critical" for f in findings)


def test_invalid_graph_critical() -> None:
    ctx = build_fastapi_todo_context(graph_validation_status="invalid")
    findings = review_implementation(ctx)
    assert any(f.finding_key == "IMPL-GRAPH-INVALID" and f.severity == "critical" for f in findings)


def test_no_dev_items_flagged() -> None:
    ctx = ReviewContext(
        project_id="p",
        work_items=[{"work_type": "qa", "id": "1", "assigned_agent_role": "qa-agent"}],
    )
    findings = review_implementation(ctx)
    assert any(f.finding_key == "IMPL-NO-DEV-ITEMS" for f in findings)
