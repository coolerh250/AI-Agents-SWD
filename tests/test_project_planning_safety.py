"""Stage 45 -- planning-only safety tests."""

from __future__ import annotations

import pytest

from project_planning_fakes import FakeProjectStore

from shared.sdk.project_planning import PlannerInput, plan_project
from shared.sdk.project_planning.routing import (
    planning_only_enabled,
    work_item_dispatch_enabled,
)


def test_planning_only_default_true() -> None:
    assert planning_only_enabled({}) is True


def test_work_item_dispatch_default_false() -> None:
    assert work_item_dispatch_enabled({}) is False


async def test_plan_does_not_dispatch_development() -> None:
    store = FakeProjectStore()
    out = await plan_project(
        PlannerInput(request_text="Create a FastAPI Todo Service with SQLite"),
        store,
        emit_events=False,
    )
    # all work items are planning_only and pending -> nothing dispatched
    items = store.work_items[out.project_id]
    assert all(w["status"] == "pending" for w in items)
    assert all(w["dispatch_policy"] in ("planning_only", "approval_required") for w in items)


async def test_plan_production_executed_false() -> None:
    store = FakeProjectStore()
    out = await plan_project(
        PlannerInput(request_text="Build a FastAPI Todo API"), store, emit_events=False
    )
    assert out.production_executed is False
    assert out.planning_only is True


def test_safety_summary_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    import operations

    monkeypatch.delenv("ENABLE_PROJECT_WORK_ITEM_DISPATCH", raising=False)
    monkeypatch.delenv("ENABLE_PROJECT_PLANNER_REAL_LLM", raising=False)
    assert operations._project_planning_flag("ENABLE_PROJECT_WORK_ITEM_DISPATCH", False) is False
    assert operations._project_planning_flag("ENABLE_PROJECT_PLANNER_REAL_LLM", False) is False
    assert operations._project_planning_flag("ENABLE_PROJECT_PLANNER", True) is True
