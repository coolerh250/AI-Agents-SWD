"""Stage 47 -- orchestrator workflow integration for workspace events."""

from __future__ import annotations

import pytest
from workflow_events import WorkflowEventConsumer


class FakeWorkflowStore:
    def __init__(self) -> None:
        self.row = {
            "task_id": "t-1",
            "stage": "design_reviewed",
            "state": {},
            "execution_result": {},
            "approval_required": False,
            "approval_status": "none",
            "risk_level": "low",
        }
        self.updated: dict | None = None

    async def get_workflow_state(self, task_id):
        return dict(self.row) if task_id == self.row["task_id"] else None

    async def update_workflow_state(self, task_id, **kwargs):
        self.row.update({"stage": kwargs["stage"]})
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


@pytest.fixture(autouse=True)
def _stub_notify(monkeypatch):
    async def _noop(*a, **k):
        return None

    monkeypatch.setattr("workflow_events.send_notification", _noop)


async def test_workspace_completed_sets_tests_passed_stage() -> None:
    store = FakeWorkflowStore()
    consumer = WorkflowEventConsumer(store=store, event_bus=FakeBus())
    out = await consumer.handle_event(
        {
            "event": "workspace.execution_completed",
            "task_id": "t-1",
            "project_id": "p1",
            "status": "tests_passed",
            "tests_status": "passed",
            "generated_files_count": 12,
        }
    )
    assert out["stage"] == "workspace_tests_passed"
    assert out["execution_result"]["production_executed"] is False
    assert out["execution_result"]["controlled_only"] is True


async def test_workspace_failed_sets_failed_stage() -> None:
    store = FakeWorkflowStore()
    consumer = WorkflowEventConsumer(store=store, event_bus=FakeBus())
    out = await consumer.handle_event(
        {"event": "workspace.execution_failed", "task_id": "t-1", "status": "failed"}
    )
    assert out["stage"] == "workspace_execution_failed"


async def test_design_review_completed_requests_workspace(monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_WORKSPACE_OPERATOR", "true")
    monkeypatch.setenv("WORKSPACE_OPERATOR_CONTROLLED_ONLY", "true")
    monkeypatch.setenv("ENABLE_PROJECT_WORK_ITEM_DISPATCH", "false")
    store = FakeWorkflowStore()
    bus = FakeBus()
    consumer = WorkflowEventConsumer(store=store, event_bus=bus)
    await consumer.handle_event(
        {
            "event": "design_review.completed",
            "task_id": "t-1",
            "project_id": "p1",
            "review_session_id": "r1",
            "decision": "planning_only",
        }
    )
    streams = [s for s, _m in bus.published]
    assert "stream.workspace_execution" in streams
    msg = next(m for s, m in bus.published if s == "stream.workspace_execution")
    assert msg["event"] == "project.workspace_execution_requested"
    assert msg["controlled_only"] is True
    assert msg["production_executed"] is False
