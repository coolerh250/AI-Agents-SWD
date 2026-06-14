"""Stage 45 -- project-planner-agent handle() tests (no Redis, no DB)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from project_planning_fakes import FakeProjectStore

_REPO = Path(__file__).resolve().parents[1]


def _load_agent_class():
    path = _REPO / "agents" / "project-planner-agent" / "src" / "agent.py"
    spec = importlib.util.spec_from_file_location("project_planner_agent_mod", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.ProjectPlannerAgent


class FakeBus:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict]] = []

    async def publish_event(self, stream: str, message: dict) -> str:
        self.published.append((stream, message))
        return "1-0"

    async def close(self) -> None:  # pragma: no cover
        pass


@pytest.fixture(autouse=True)
def _stub_network(monkeypatch: pytest.MonkeyPatch):
    async def _noop_audit(**kwargs):
        return None

    async def _noop_notify(*args, **kwargs):
        return None

    monkeypatch.setattr("shared.sdk.audit.publisher.publish_audit_event", _noop_audit)
    monkeypatch.setattr("shared.sdk.notifications.client.send_notification", _noop_notify)


def _make_agent():
    cls = _load_agent_class()
    agent = cls(event_bus=FakeBus())
    agent._store = FakeProjectStore()
    return agent


async def test_agent_plans_fastapi_todo() -> None:
    agent = _make_agent()
    result = await agent.handle(
        {
            "task_id": "t-1",
            "request": {"type": "software_project", "description": "Create a FastAPI Todo Service"},
        }
    )
    assert result["result"] == "completed"
    assert result["artifact_refs"]["production_executed"] is False
    assert result["artifact_refs"]["work_items_count"] >= 8
    assert result["event_type"] == "project.planning_completed"
    # planner published a completion event to stream.project_events
    streams = [s for (s, _m) in agent.bus.published]
    assert "stream.project_events" in streams


async def test_agent_clarification_path() -> None:
    agent = _make_agent()
    result = await agent.handle(
        {"task_id": "t-2", "request": {"type": "software_project", "description": "todo"}}
    )
    assert result["result"] == "requires_clarification"
    assert result["event_type"] == "project.clarification_required"


async def test_agent_never_executes_production() -> None:
    agent = _make_agent()
    await agent.handle(
        {"task_id": "t-3", "request": {"description": "Build a FastAPI Todo API with SQLite"}}
    )
    for _stream, msg in agent.bus.published:
        assert msg.get("production_executed") is False
        assert msg.get("planning_only") is True
