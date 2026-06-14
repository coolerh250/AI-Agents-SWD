"""Stage 46 -- acceptance coverage tests."""

from __future__ import annotations

from design_review_fakes import build_fastapi_todo_context

from shared.sdk.design_review.acceptance_coverage import (
    compute_acceptance_coverage,
    review_acceptance_coverage,
)
from shared.sdk.design_review.models import ReviewContext


def test_fastapi_todo_coverage() -> None:
    cov = compute_acceptance_coverage(build_fastapi_todo_context())
    assert cov.total == 10
    assert cov.required == 10
    assert cov.mapped == 8
    assert cov.unmapped == 2
    assert cov.coverage_percent == 80.0


def test_no_required_criteria_flags_high() -> None:
    ctx = ReviewContext(project_id="p", acceptance_criteria=[])
    _cov, findings = review_acceptance_coverage(ctx)
    assert any(f.finding_key == "AC-NONE-REQUIRED" and f.severity == "high" for f in findings)


def test_low_coverage_flags_medium() -> None:
    ctx = ReviewContext(
        project_id="p",
        acceptance_criteria=[
            {"required": True, "work_item_id": None},
            {"required": True, "work_item_id": None},
            {"required": True, "work_item_id": "w1"},
        ],
    )
    cov, findings = review_acceptance_coverage(ctx)
    assert cov.coverage_percent < 50.0
    assert any(f.finding_key == "AC-LOW-COVERAGE" for f in findings)
