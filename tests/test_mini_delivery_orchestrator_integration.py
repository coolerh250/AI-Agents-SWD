"""Stage 48 -- orchestrator workflow integration for delivery pilot events."""

from __future__ import annotations

import pytest
from workflow_events import WorkflowEventConsumer


class FakeWorkflowStore:
    def __init__(self) -> None:
        self.row = {
            "task_id": "t-1",
            "stage": "in_progress",
            "state": {},
            "execution_result": {},
            "approval_required": False,
            "approval_status": "none",
            "risk_level": "low",
        }

    async def get_workflow_state(self, task_id):
        return dict(self.row) if task_id == self.row["task_id"] else None

    async def update_workflow_state(self, task_id, **kwargs):
        self.row["stage"] = kwargs["stage"]
        return {"task_id": task_id, **kwargs}


class FakeBus:
    def __init__(self) -> None:
        self.published: list = []

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


async def test_delivery_pilot_completed_sets_stage() -> None:
    consumer = WorkflowEventConsumer(store=FakeWorkflowStore(), event_bus=FakeBus())
    out = await consumer.handle_event(
        {
            "event": "delivery_pilot.completed",
            "task_id": "t-1",
            "pilot_id": "p1",
            "pilot_status": "completed",
            "qa_status": "passed",
            "safety_status": "safe",
            "acceptance_total": 10,
            "acceptance_satisfied": 10,
        }
    )
    assert out["stage"] == "mini_delivery_pilot_completed"
    assert out["execution_result"]["production_executed"] is False
    assert out["execution_result"]["controlled_only"] is True


async def test_delivery_pilot_failed_sets_stage() -> None:
    consumer = WorkflowEventConsumer(store=FakeWorkflowStore(), event_bus=FakeBus())
    out = await consumer.handle_event(
        {"event": "delivery_pilot.failed", "task_id": "t-1", "pilot_status": "blocked"}
    )
    assert out["stage"] == "mini_delivery_pilot_failed"
