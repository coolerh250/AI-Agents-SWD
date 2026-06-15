"""Stage 48 -- pilot step tracker helpers."""

from __future__ import annotations

from shared.sdk.mini_delivery_pilot.step_tracker import (
    PILOT_STEP_ORDER,
    STEP_TYPES_BY_KEY,
    make_step,
)


def test_step_order_and_types() -> None:
    assert PILOT_STEP_ORDER[0] == "project_plan"
    assert PILOT_STEP_ORDER[-1] == "pilot_report"
    for key in PILOT_STEP_ORDER:
        assert key in STEP_TYPES_BY_KEY


def test_make_step_maps_type() -> None:
    s = make_step("design_review", "passed", summary="ok")
    assert s.step_type == "review"
    assert s.status == "passed"
    assert s.summary == "ok"
    assert make_step("workspace_execution", "passed").step_type == "implementation"
    assert make_step("acceptance_evaluation", "passed").step_type == "acceptance"
