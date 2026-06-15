"""Stage 48 -- mini-delivery-pilot-agent handle() (no Redis, fakes + tmp fs)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from design_review_fakes import FakeDesignReviewStore, FakeDiscussionStore
from mini_delivery_fakes import FakeMiniDeliveryPilotStore
from project_planning_fakes import FakeProjectStore
from workspace_operator_fakes import FakeWorkspaceStore

_REPO = Path(__file__).resolve().parents[1]


def _load_agent_class():
    path = _REPO / "agents" / "mini-delivery-pilot-agent" / "src" / "agent.py"
    spec = importlib.util.spec_from_file_location("mini_delivery_pilot_agent_mod", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.MiniDeliveryPilotAgent


class FakeBus:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict]] = []

    async def publish_event(self, stream, message):
        self.published.append((stream, message))
        return "1-0"

    async def close(self):  # pragma: no cover
        pass


@pytest.fixture(autouse=True)
def _stub_network(monkeypatch):
    async def _noop(*a, **k):
        return None

    monkeypatch.setattr("shared.sdk.audit.publisher.publish_audit_event", _noop)
    monkeypatch.setattr("shared.sdk.notifications.client.send_notification", _noop)


async def test_agent_runs_full_pilot(tmp_path, monkeypatch) -> None:
    root = tmp_path / "aiagents-workspaces"
    root.mkdir()
    monkeypatch.setenv("WORKSPACE_OPERATOR_ALLOWED_ROOTS", str(root))
    cls = _load_agent_class()
    agent = cls(event_bus=FakeBus())
    agent._project_store = FakeProjectStore()
    agent._discussion_store = FakeDiscussionStore()
    agent._review_store = FakeDesignReviewStore()
    agent._workspace_store = FakeWorkspaceStore()
    agent._pilot_store = FakeMiniDeliveryPilotStore()

    result = await agent.handle({"task_id": "t-1"})
    assert result["result"] in ("completed", "report_ready")
    assert result["event_type"] == "delivery_pilot.completed"
    assert result["artifact_refs"]["production_executed"] is False
    streams = [s for s, _m in agent.bus.published]
    assert "stream.delivery_pilot_events" in streams
    for _stream, msg in agent.bus.published:
        assert msg.get("production_executed") is False
        assert msg.get("pr_created") is False
        assert msg.get("deployment_performed") is False
        assert msg.get("real_llm_used") is False
