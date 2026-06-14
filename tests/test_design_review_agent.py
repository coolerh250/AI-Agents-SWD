"""Stage 46 -- design-review-agent handle() tests (no Redis, no DB)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from design_review_fakes import (
    FakeDesignReviewStore,
    FakeDiscussionStore,
    populate_project_store,
)
from project_planning_fakes import FakeProjectStore

_REPO = Path(__file__).resolve().parents[1]


def _load_agent_class():
    path = _REPO / "agents" / "design-review-agent" / "src" / "agent.py"
    spec = importlib.util.spec_from_file_location("design_review_agent_mod", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.DesignReviewAgent


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
    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr("shared.sdk.audit.publisher.publish_audit_event", _noop)
    monkeypatch.setattr("shared.sdk.notifications.client.send_notification", _noop)


async def _make_agent():
    cls = _load_agent_class()
    agent = cls(event_bus=FakeBus())
    project_store = FakeProjectStore()
    project_id = await populate_project_store(project_store)
    agent._project_store = project_store
    agent._discussion_store = FakeDiscussionStore()
    agent._review_store = FakeDesignReviewStore()
    return agent, project_id


async def test_agent_runs_design_review() -> None:
    agent, project_id = await _make_agent()
    result = await agent.handle({"task_id": "t-1", "project_id": project_id})
    assert result["result"] in ("passed", "passed_with_findings")
    assert result["artifact_refs"]["production_executed"] is False
    assert result["event_type"] == "design_review.completed"
    streams = [s for s, _m in agent.bus.published]
    assert "stream.design_review_events" in streams


async def test_agent_published_message_is_planning_only() -> None:
    agent, project_id = await _make_agent()
    await agent.handle({"task_id": "t-2", "project_id": project_id})
    for _stream, msg in agent.bus.published:
        assert msg.get("production_executed") is False
        assert msg.get("planning_only") is True


async def test_agent_missing_project_id_blocked() -> None:
    agent, _ = await _make_agent()
    result = await agent.handle({"task_id": "t-3"})
    assert result["result"] == "failed"
    assert result["event_type"] == "design_review.blocked"
