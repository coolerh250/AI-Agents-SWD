"""Stage 46 -- orchestrator design review workflow integration tests."""

from __future__ import annotations

import importlib

import pytest


def _we():
    return importlib.import_module("workflow_events")


class FakeWorkflowStore:
    def __init__(self) -> None:
        self.updated: dict | None = None

    async def update_workflow_state(self, task_id, **kwargs):
        self.updated = {"task_id": task_id, **kwargs}
        return self.updated


class FakeBus:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict]] = []

    async def publish_event(self, stream, message):
        self.published.append((stream, message))
        return "1-0"

    async def close(self):  # pragma: no cover
        pass


async def _noop_notify(*args, **kwargs):
    return None


def _workflow(stage="in_progress"):
    return {
        "task_id": "t-1",
        "stage": stage,
        "state": {},
        "execution_result": {},
        "approval_required": False,
        "approval_status": "none",
        "risk_level": "low",
    }


async def test_planning_completed_triggers_design_review(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_DESIGN_REVIEW", "true")
    we = _we()
    monkeypatch.setattr(we, "send_notification", _noop_notify)
    bus = FakeBus()
    consumer = we.WorkflowEventConsumer(store=FakeWorkflowStore(), event_bus=bus)
    await consumer._advance(
        _workflow(),
        "project.planning_completed",
        {
            "project_id": "p-1",
            "graph_snapshot_id": "g-1",
            "validation_status": "valid",
            "work_items_count": 9,
        },
    )
    streams = [s for s, _m in bus.published]
    assert "stream.design_review" in streams


async def test_design_review_completed_sets_stage(monkeypatch: pytest.MonkeyPatch) -> None:
    we = _we()
    monkeypatch.setattr(we, "send_notification", _noop_notify)
    consumer = we.WorkflowEventConsumer(store=FakeWorkflowStore(), event_bus=FakeBus())
    updated = await consumer._advance(
        _workflow(),
        "design_review.completed",
        {
            "project_id": "p-1",
            "review_session_id": "r-1",
            "decision": "planning_only",
            "findings_count": 3,
            "gates_count": 7,
        },
    )
    assert updated["stage"] == "design_reviewed"
    assert updated["execution_result"]["production_executed"] is False


async def test_design_review_blocked_sets_blocked_stage(monkeypatch: pytest.MonkeyPatch) -> None:
    we = _we()
    monkeypatch.setattr(we, "send_notification", _noop_notify)
    consumer = we.WorkflowEventConsumer(store=FakeWorkflowStore(), event_bus=FakeBus())
    updated = await consumer._advance(
        _workflow(),
        "design_review.blocked",
        {"project_id": "p-1", "decision": "no_go"},
    )
    assert updated["stage"] == "design_review_blocked"


async def test_go_with_findings_stage(monkeypatch: pytest.MonkeyPatch) -> None:
    we = _we()
    monkeypatch.setattr(we, "send_notification", _noop_notify)
    consumer = we.WorkflowEventConsumer(store=FakeWorkflowStore(), event_bus=FakeBus())
    updated = await consumer._advance(
        _workflow(),
        "design_review.completed",
        {"project_id": "p-1", "decision": "go_with_findings"},
    )
    assert updated["stage"] == "design_reviewed_with_findings"
