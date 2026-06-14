"""Stage 45 -- project planning Pydantic model tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from shared.sdk.project_planning.models import (
    AcceptanceCriterion,
    PlannerOutput,
    ProjectBrief,
    ProjectCreate,
    ProjectWorkItem,
    UserStory,
    WorkItemDependency,
)


def test_project_create_defaults() -> None:
    p = ProjectCreate(title="x")
    assert p.status == "draft"
    assert p.autonomy_level == "autonomous_dev_test"
    assert p.risk_level == "low"
    assert p.metadata == {}


def test_brief_round_trip() -> None:
    b = ProjectBrief(goal="g", scope=["a"], non_scope=["b"])
    assert b.scope == ["a"]
    assert b.non_scope == ["b"]
    assert b.requires_clarification is False


def test_models_reject_unknown_field() -> None:
    with pytest.raises(ValidationError):
        ProjectCreate(title="x", bogus=1)  # type: ignore[call-arg]


def test_work_item_and_dependency() -> None:
    w = ProjectWorkItem(work_item_key="BE-001", title="impl")
    assert w.dispatch_policy == "planning_only"
    assert w.status == "pending"
    d = WorkItemDependency(work_item_key="A", depends_on_work_item_key="B")
    assert d.dependency_type == "blocks"


def test_user_story_and_acceptance() -> None:
    s = UserStory(story_key="US-1", actor="user", need="do x")
    assert s.status == "draft"
    c = AcceptanceCriterion(criterion_key="AC-1", description="works")
    assert c.required is True
    assert c.status == "pending"


def test_planner_output_production_executed_false() -> None:
    out = PlannerOutput(project_id="p1")
    assert out.production_executed is False
    assert out.planning_only is True
