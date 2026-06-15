"""Stage 49 -- orchestrator workflow integration for delivery package events."""

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


async def test_delivery_package_ready_sets_stage() -> None:
    consumer = WorkflowEventConsumer(store=FakeWorkflowStore(), event_bus=FakeBus())
    out = await consumer.handle_event(
        {
            "event": "delivery_package.ready_for_review",
            "task_id": "t-1",
            "package_id": "pkg1",
            "package_status": "ready_for_review",
            "acceptance_gate_decision": "ready_for_operator_review",
            "human_acceptance_status": "pending",
            "readiness_status": "ready_for_operator_review",
        }
    )
    assert out["stage"] == "delivery_package_ready_for_review"
    assert out["execution_result"]["production_executed"] is False
    assert out["execution_result"]["controlled_only"] is True
    assert out["execution_result"]["delivery_package"]["human_acceptance_status"] == "pending"


async def test_delivery_package_failed_sets_stage() -> None:
    consumer = WorkflowEventConsumer(store=FakeWorkflowStore(), event_bus=FakeBus())
    out = await consumer.handle_event(
        {"event": "delivery_package.build_failed", "task_id": "t-1", "package_status": "blocked"}
    )
    assert out["stage"] == "delivery_package_failed"


async def test_completed_pilot_requests_package_build(monkeypatch) -> None:
    monkeypatch.setattr("workflow_events.send_notification", _noop_async)
    bus = FakeBus()
    consumer = WorkflowEventConsumer(store=FakeWorkflowStore(), event_bus=bus)
    await consumer.handle_event(
        {
            "event": "delivery_pilot.completed",
            "task_id": "t-1",
            "pilot_id": "p1",
            "project_id": "proj1",
            "pilot_status": "completed",
        }
    )
    streams = [s for s, _m in bus.published]
    assert "stream.delivery_package" in streams


async def _noop_async(*a, **k):
    return None
