"""Stage 46 -- architecture reviewer tests."""

from __future__ import annotations

from design_review_fakes import build_fastapi_todo_context

from shared.sdk.design_review.architecture_reviewer import review_architecture
from shared.sdk.design_review.models import ReviewContext


def test_fastapi_todo_architecture_clean() -> None:
    # architecture + backend + database + deps present
    findings = review_architecture(build_fastapi_todo_context())
    assert findings == []


def test_missing_architecture_item_flags_high() -> None:
    ctx = ReviewContext(
        project_id="p",
        work_items=[{"work_type": "qa", "id": "1"}],
        dependencies=[{"work_item_id": "1", "depends_on_work_item_id": "1"}],
    )
    findings = review_architecture(ctx)
    assert any(f.finding_key == "ARCH-NO-DESIGN" and f.severity == "high" for f in findings)


def test_no_dependencies_flagged() -> None:
    ctx = ReviewContext(
        project_id="p",
        work_items=[{"work_type": "architecture", "id": "1"}, {"work_type": "backend", "id": "2"}],
        dependencies=[],
    )
    findings = review_architecture(ctx)
    assert any(f.finding_key == "ARCH-NO-DEPS" for f in findings)
