"""Stage 46 -- design review model tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from shared.sdk.design_review.models import (
    DesignReviewFinding,
    DesignReviewOutput,
    GoNoGoSummary,
    ProjectReviewGate,
)


def test_finding_defaults() -> None:
    f = DesignReviewFinding(
        finding_key="F1", finding_type="security_risk", title="t", description="d"
    )
    assert f.severity == "low"
    assert f.status == "open"


def test_gate_defaults() -> None:
    g = ProjectReviewGate(gate_type="security_gate")
    assert g.required is True
    assert g.blocking is True


def test_output_production_executed_false() -> None:
    o = DesignReviewOutput(project_id="p1")
    assert o.production_executed is False
    assert o.planning_only is True
    assert o.work_item_dispatch_enabled is False


def test_go_no_go_summary_defaults() -> None:
    s = GoNoGoSummary()
    assert s.production_executed is False
    assert s.planning_only is True


def test_reject_unknown_field() -> None:
    with pytest.raises(ValidationError):
        ProjectReviewGate(gate_type="x", bogus=1)  # type: ignore[call-arg]
