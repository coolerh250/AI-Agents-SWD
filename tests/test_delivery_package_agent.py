"""Stage 49 -- delivery-package-agent handle() (no Redis, fakes + tmp fs)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from delivery_package_fakes import FakeDeliveryPackageStore
from mini_delivery_fakes import run_fake_pilot

_REPO = Path(__file__).resolve().parents[1]


def _load_agent_class():
    path = _REPO / "agents" / "delivery-package-agent" / "src" / "agent.py"
    spec = importlib.util.spec_from_file_location("delivery_package_agent_mod", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.DeliveryPackageAgent


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


async def test_agent_builds_package(tmp_path, monkeypatch) -> None:
    pilot_result, stores = await run_fake_pilot(tmp_path, monkeypatch)
    cls = _load_agent_class()
    agent = cls(event_bus=FakeBus())
    agent._pilot_store = stores["pilot"]
    agent._project_store = stores["project"]
    agent._review_store = stores["review"]
    agent._workspace_store = stores["workspace"]
    agent._package_store = FakeDeliveryPackageStore()

    result = await agent.handle({"task_id": "t-1", "pilot_id": pilot_result.pilot_id})
    assert result["result"] == "ready_for_review"
    assert result["event_type"] == "delivery_package.ready_for_review"
    assert result["artifact_refs"]["production_executed"] is False
    assert result["artifact_refs"]["human_acceptance_status"] == "pending"
    streams = [s for s, _m in agent.bus.published]
    assert "stream.delivery_package_events" in streams
    for _stream, msg in agent.bus.published:
        assert msg.get("production_executed") is False
        assert msg.get("pr_created") is False
        assert msg.get("deployment_performed") is False
        assert msg.get("real_llm_used") is False
        assert msg.get("external_delivery_performed") is False


async def test_agent_refuses_without_pilot_id(tmp_path, monkeypatch) -> None:
    cls = _load_agent_class()
    agent = cls(event_bus=FakeBus())
    result = await agent.handle({"task_id": "t-1"})
    assert result["result"] == "failed"
    assert "pilot_id_required" in result["message"]
