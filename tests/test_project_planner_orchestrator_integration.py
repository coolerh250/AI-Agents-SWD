"""Stage 45 -- orchestrator routing + workflow advance integration tests."""

from __future__ import annotations

import pytest

from shared.sdk.project_planning.routing import (
    should_route_to_project_planner,
)


def test_project_types_route_to_planner() -> None:
    for rtype in ("software_project", "feature_request", "build_request"):
        assert should_route_to_project_planner(request_type=rtype, request_text="x") is True


def test_legacy_types_stay_on_legacy_path() -> None:
    for rtype in ("dev.test", "production.deploy", "bugfix", "unknown"):
        assert should_route_to_project_planner(request_type=rtype, request_text="x") is False


def test_skip_flag_disables_routing() -> None:
    assert (
        should_route_to_project_planner(
            request_type="software_project", request_text="x", skip_project_planning=True
        )
        is False
    )


def test_feature_flag_disabled_falls_back_to_legacy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_PROJECT_PLANNER", "false")
    assert (
        should_route_to_project_planner(request_type="software_project", request_text="x") is False
    )


def _load_workflow_events():
    import importlib

    return importlib.import_module("workflow_events")


class FakeWorkflowStore:
    def __init__(self, stage: str = "in_progress") -> None:
        self.updated: dict | None = None
        self._stage = stage

    async def update_workflow_state(self, task_id, **kwargs):
        self.updated = {"task_id": task_id, **kwargs}
        return self.updated


async def test_project_completed_event_sets_project_planned_stage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    we = _load_workflow_events()
    monkeypatch.setattr(we, "send_notification", _noop_notify)
    consumer = we.WorkflowEventConsumer(store=FakeWorkflowStore(), event_bus=_FakeBus())
    workflow = {
        "task_id": "t-1",
        "stage": "in_progress",
        "state": {},
        "execution_result": {},
        "approval_required": False,
        "approval_status": "none",
        "risk_level": "low",
    }
    updated = await consumer._advance(
        workflow,
        "project.planning_completed",
        {
            "project_id": "p-1",
            "graph_snapshot_id": "g-1",
            "validation_status": "valid",
            "work_items_count": 9,
        },
    )
    assert updated["stage"] == "project_planned"
    assert updated["execution_result"]["production_executed"] is False
    assert updated["execution_result"]["project_planning"]["project_id"] == "p-1"


async def test_invalid_graph_sets_planning_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    we = _load_workflow_events()
    monkeypatch.setattr(we, "send_notification", _noop_notify)
    consumer = we.WorkflowEventConsumer(store=FakeWorkflowStore(), event_bus=_FakeBus())
    workflow = {
        "task_id": "t-2",
        "stage": "in_progress",
        "state": {},
        "execution_result": {},
        "approval_required": False,
        "approval_status": "none",
        "risk_level": "low",
    }
    updated = await consumer._advance(
        workflow,
        "project.planning_completed",
        {"project_id": "p-2", "validation_status": "invalid"},
    )
    assert updated["stage"] == "planning_failed"


async def _noop_notify(*args, **kwargs):
    return None


class _FakeBus:
    async def close(self):  # pragma: no cover
        pass
